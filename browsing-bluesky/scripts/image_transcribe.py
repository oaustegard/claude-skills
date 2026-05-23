#!/usr/bin/env python3
"""Image transcription helper for Bluesky embed images.

Downloads an image from the bsky CDN (or any URL) and returns a text
transcription via a chosen model. Used opportunistically by bsky.py when
posts have images with missing or empty alt text.

The model is chosen by the caller via `model_alias`. Empirical results on
dense terminal screenshots (May 2026, n=3 images, single run each):

    alias              latency   $/image   chord-token recall   notes
    -------------------------------------------------------------------
    'gemini-lite'         ~8s   ~$0.001   95%                  best Pareto for routine
    'gemini-flash'       ~10s   ~$0.003   100%                 token-perfect, still cheap
    'gemini-3.5-flash'   ~10s   ~$0.014   100%                 frontier, premium cost
    'haiku'               ~7s   ~$0.008   18%                  weak prompt-following: summarizes
    'opus'               ~20s   ~$0.12    91%                  use for interactive only

Pick `'gemini-lite'` for routine work, `'gemini-flash'` if you need
token-perfect transcription cheaply, `'gemini-3.5-flash'` if you need
frontier-tier reasoning alongside the transcription, `'opus'` for
interactive contexts where conversation history matters, `'haiku'` only
if you're constrained to a single-vendor Anthropic deployment.

Failure policy: any error (download, encoding, API call) returns None
rather than raising, so the caller can degrade gracefully.
"""

import base64
import sys
import urllib.request
from typing import Optional

# Defer Anthropic + Gemini client imports to call-time so the module loads
# cleanly in environments where their dependencies aren't on sys.path.
_CLAUDE_CLIENT_PATH = "/mnt/skills/user/orchestrating-agents/scripts"
_GEMINI_CLIENT_PATH = "/mnt/skills/user/invoking-gemini/scripts"

# Model aliases → backend + model identifier. The backend tag selects the
# routing path (Anthropic Messages API vs. Gemini via Cloudflare AI Gateway).
_MODEL_REGISTRY = {
    # Anthropic
    "haiku": ("anthropic", "claude-haiku-4-5-20251001"),
    "opus":  ("anthropic", "claude-opus-4-7"),
    # Gemini — recommended order: lite for routine, flash for token-perfect,
    # 3.5-flash for premium reasoning alongside transcription.
    "gemini-lite":       ("gemini", "gemini-2.5-flash-lite"),
    "gemini-flash":      ("gemini", "gemini-2.5-flash"),
    "gemini-3.5-flash":  ("gemini", "gemini-3.5-flash"),
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


def _call_anthropic(model: str, data: bytes, ctype: str, max_tokens: int) -> Optional[str]:
    """Anthropic Messages API path."""
    if _CLAUDE_CLIENT_PATH not in sys.path:
        sys.path.insert(0, _CLAUDE_CLIENT_PATH)
    try:
        from claude_client import invoke_claude
    except ImportError:
        return None

    b64 = base64.standard_b64encode(data).decode("ascii")
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": ctype, "data": b64}},
        {"type": "text", "text": _TRANSCRIBE_PROMPT},
    ]
    try:
        return invoke_claude(content, model=model, max_tokens=max_tokens).strip()
    except Exception:
        return None


def _call_gemini(model: str, data: bytes, ctype: str, max_tokens: int) -> Optional[str]:
    """Gemini path via the invoking-gemini client.

    Writes the bytes to a temp file because invoke_gemini takes image_path,
    not raw bytes. (The download has already happened — this is just an
    interface mismatch.) Uses thinking_level='minimal' since transcription
    doesn't need reasoning; without this, Gemini 3.x silently spends output
    tokens on thinking and truncates.
    """
    if _GEMINI_CLIENT_PATH not in sys.path:
        sys.path.insert(0, _GEMINI_CLIENT_PATH)
    try:
        from gemini_client import invoke_gemini
    except ImportError:
        return None

    import tempfile, os as _os
    suffix = {"image/png": ".png", "image/jpeg": ".jpg",
              "image/webp": ".webp", "image/gif": ".gif"}.get(ctype, ".png")
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(data)
        tmp.close()
        out = invoke_gemini(
            prompt=_TRANSCRIBE_PROMPT,
            model=model,
            image_path=tmp.name,
            max_output_tokens=max_tokens,
            thinking_level="minimal",  # transcription doesn't need reasoning
        )
        return out.strip() if out else None
    except Exception:
        return None
    finally:
        try:
            _os.unlink(tmp.name)
        except OSError:
            pass


def transcribe_image(
    url: str,
    model_alias: str = "gemini-lite",
    max_tokens: int = 4000,
    timeout: float = 15.0,
) -> Optional[str]:
    """Download `url` and transcribe it via the chosen model.

    Args:
        url: Image URL (bsky CDN or otherwise). Must be reachable via HTTP(S).
        model_alias: One of 'gemini-lite' (default — cheapest, fastest, ~95%
            chord-token recall), 'gemini-flash' (token-perfect, ~3x cost),
            'gemini-3.5-flash' (frontier reasoning, ~19x cost), 'haiku'
            (Anthropic single-vendor option, weak prompt-following on dense
            transcription), 'opus' (Anthropic, interactive use). Unrecognized
            aliases default to 'gemini-lite' to avoid surprise costs.
        max_tokens: Response cap. Bumped from 1000 → 4000 because dense
            screenshots need it; Gemini thinking-level=minimal keeps cost
            proportional to actual output.
        timeout: Download timeout in seconds.

    Returns:
        The transcription string, or None on any failure (network, decode,
        unsupported media type, API error). Errors are intentionally silent —
        the caller decides whether missing transcription is fatal.
    """
    routing = _MODEL_REGISTRY.get(model_alias, _MODEL_REGISTRY["gemini-lite"])
    backend, model = routing

    fetched = _download(url, timeout=timeout)
    if fetched is None:
        return None
    data, ctype = fetched

    if backend == "anthropic":
        return _call_anthropic(model, data, ctype, max_tokens)
    elif backend == "gemini":
        return _call_gemini(model, data, ctype, max_tokens)
    return None
