#!/usr/bin/env python3
"""Image transcription helper for Bluesky embed images.

Downloads an image from the bsky CDN (or any URL), encodes it for the Anthropic
Messages API, and returns a text transcription. Used opportunistically by
bsky.py when posts have images with missing or empty alt text.

The model is chosen by the caller via `model_alias`:
  - 'haiku' → Haiku 4.5: ~10x cheaper than Opus, ~3x faster, good enough for
    routine triage (zeitgeist runs, inbox review, news scanning).
  - 'opus'  → Opus 4.7: higher fidelity OCR and richer scene interpretation;
    use for interactive sessions where the image is part of the active task.

Failure policy: any error (download, encoding, API call) returns None rather
than raising, so the caller can degrade gracefully. The caller is responsible
for logging if it cares.
"""

import base64
import sys
import urllib.request
from typing import Optional

# Defer the orchestrating-agents import to call-time so the module loads cleanly
# in environments where claude_client.py isn't on sys.path. The boot script
# wires it in via the .pth file, but explicit fallback is cheap insurance.
_CLAUDE_CLIENT_PATH = "/mnt/skills/user/orchestrating-agents/scripts"

# Default models per alias. Pinned to the dated Haiku release because the
# unversioned alias has resolved differently in past releases; Opus uses the
# current major (4-7) per system catalog as of 2026-05-23.
_MODEL_BY_ALIAS = {
    "haiku": "claude-haiku-4-5-20251001",
    "opus": "claude-opus-4-7",
}

# Anthropic Messages API supported image media types.
_SUPPORTED_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

# Bsky CDN serves WebP by default. Hard cap at 5 MB to stay well under the
# 5 MB-per-image base64 limit and to bound a misbehaving URL's cost.
_MAX_BYTES = 5 * 1024 * 1024

# Transcription prompt is intentionally tight: extract text content + structure,
# avoid prose interpretation. Prose framing belongs in the main model that
# called us, not in the transcriber.
_TRANSCRIBE_PROMPT = (
    "Transcribe this image. Focus on extracting all text content "
    "(code, terminal output, UI labels, file paths, command-line flags, "
    "chord names, timestamps). Preserve structure (tables, columns, "
    "ordered lists, indentation). Be specific about what tool or UI is in "
    "view (window title, app name, prompt context). If the image is purely "
    "pictorial (no text), describe what is depicted concretely. "
    "Under 250 words."
)


def _download(url: str, timeout: float = 15.0) -> Optional[tuple[bytes, str]]:
    """Fetch image bytes + content-type from URL. Returns None on any error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "muninn-raven"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            data = resp.read(_MAX_BYTES + 1)
        if len(data) > _MAX_BYTES:
            return None  # Too large; reject rather than silently truncate.
        if ctype not in _SUPPORTED_MEDIA_TYPES:
            # Bsky CDN sometimes omits or mangles the content-type header.
            # Sniff the magic bytes for the common cases.
            if data.startswith(b"RIFF") and b"WEBP" in data[:32]:
                ctype = "image/webp"
            elif data.startswith(b"\x89PNG\r\n\x1a\n"):
                ctype = "image/png"
            elif data[:3] == b"\xff\xd8\xff":
                ctype = "image/jpeg"
            elif data[:6] in (b"GIF87a", b"GIF89a"):
                ctype = "image/gif"
            else:
                return None
        return data, ctype
    except Exception:
        return None


def transcribe_image(
    url: str,
    model_alias: str = "haiku",
    max_tokens: int = 1000,
    timeout: float = 15.0,
) -> Optional[str]:
    """Download `url` and ask Claude to transcribe it.

    Args:
        url: Image URL (bsky CDN or otherwise). Must be reachable via HTTP(S).
        model_alias: 'haiku' (cheap, routine) or 'opus' (expensive, interactive).
            Unrecognized aliases default to 'haiku' to avoid surprise costs.
        max_tokens: Response cap. 1000 tokens is enough for a screen of text.
        timeout: Download timeout in seconds.

    Returns:
        The transcription string, or None on any failure (network, decode,
        unsupported media type, API error). Errors are intentionally silent —
        the caller decides whether missing transcription is fatal.
    """
    if _CLAUDE_CLIENT_PATH not in sys.path:
        sys.path.insert(0, _CLAUDE_CLIENT_PATH)
    try:
        from claude_client import invoke_claude
    except ImportError:
        return None

    fetched = _download(url, timeout=timeout)
    if fetched is None:
        return None
    data, ctype = fetched

    model = _MODEL_BY_ALIAS.get(model_alias, _MODEL_BY_ALIAS["haiku"])
    b64 = base64.standard_b64encode(data).decode("ascii")

    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": ctype,
                "data": b64,
            },
        },
        {"type": "text", "text": _TRANSCRIBE_PROMPT},
    ]

    try:
        return invoke_claude(content, model=model, max_tokens=max_tokens).strip()
    except Exception:
        return None
