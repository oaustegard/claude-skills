#!/usr/bin/env python3
"""Image transcription helper for Bluesky embed images.

Downloads an image from the bsky CDN (or any URL) and returns a text
transcription via a chosen model. Used opportunistically by bsky.py when
posts have images with missing or empty alt text.

The model is chosen by the caller via `model_alias`. Gemini rows re-measured
2026-11-20 on 3 synthetic terminal/table screenshots (clean text, single run
each). All three Gemini models scored 100% token recall, so this set shows cost
and speed, not accuracy differences:

    alias              model                  latency   $/image   recall
    ----------------------------------------------------------------------
    'gemini-lite'      gemini-3.5-flash-lite     ~2s   ~$0.0009   100%
    'gemini-flash'     gemini-4-hydrogen         ~6s   ~$0.007    100%   thinks ~400-560 tokens at 'low'
    'haiku'            claude-haiku-5-5          ~7s   ~$0.008     18%   summarizes (May 2026, Haiku 4.5)
    'opus'             claude-opus-5-5          ~20s   ~$0.12      91%   interactive only (May 2026, Opus 4.7)

Pick `'gemini-lite'` for routine work. Pick `'gemini-flash'` when the image needs
interpretation as well as reading; it costs about 8x lite. `'gemini-3.5-flash'`
also runs gemini-4-hydrogen (that model is retired; the name is kept for callers). `'opus'` is for interactive
contexts where conversation history matters, and `'haiku'` only for a
single-vendor Anthropic deployment. The haiku and opus rows are from May 2026 on
Haiku 4.5 and Opus 4.7 and have not been re-measured.

Failure policy: any error (download, encoding, API call) returns None
rather than raising, so the caller can degrade gracefully.
"""

import base64
import sys
import urllib.request

# Defer Anthropic + Gemini client imports to call-time so the module loads
# cleanly in environments where their dependencies aren't on sys.path.
_CLAUDE_CLIENT_PATH = "/mnt/skills/user/orchestrating-chat-agents/scripts"
_GEMINI_CLIENT_PATH = "/mnt/skills/user/invoking-gemini/scripts"

# Model aliases → backend + model identifier. The backend tag selects the
# routing path (Anthropic Messages API vs. Gemini via Cloudflare AI Gateway).
_MODEL_REGISTRY = {
    # Anthropic
    "haiku": ("anthropic", "claude-haiku-5-5"),
    "opus":  ("anthropic", "claude-opus-5-5"),
    # Gemini — lite for routine reading, flash when the image needs interpreting.
    # `gemini-3.5-flash` is an old name kept for callers; it now means flash.
    # Re-pointed 2026-11-20 off the retired 2.5 and 3.5 Flash models.
    "gemini-lite":       ("gemini", "gemini-3.5-flash-lite"),
    "gemini-flash":      ("gemini", "gemini-4-hydrogen"),
    "gemini-3.5-flash":  ("gemini", "gemini-4-hydrogen"),
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


def _download(url: str, timeout: float = 15.0) -> tuple[bytes, str] | None:
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


def _call_anthropic(model: str, data: bytes, ctype: str, max_tokens: int) -> str | None:
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


def _call_gemini(model: str, data: bytes, ctype: str, max_tokens: int) -> str | None:
    """Gemini path via the invoking-gemini client.

    Writes the bytes to a temp file because invoke_gemini takes image_path,
    not raw bytes. (The download has already happened — this is just an
    interface mismatch.) Uses the lowest thinking level each model accepts:
    'minimal' on 3.5 Flash-Lite, 'low' on Gemini 4 (which rejects 'minimal').
    Without this the model silently spends output tokens on thinking and
    truncates.
    """
    if _GEMINI_CLIENT_PATH not in sys.path:
        sys.path.insert(0, _GEMINI_CLIENT_PATH)
    try:
        from gemini_client import invoke_gemini
    except ImportError:
        return None

    import os as _os
    import tempfile
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
            # transcription doesn't need reasoning; only lite accepts 'minimal'
            thinking_level="minimal" if "flash-lite" in model else "low",
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
) -> str | None:
    """Download `url` and transcribe it via the chosen model.

    Args:
        url: Image URL (bsky CDN or otherwise). Must be reachable via HTTP(S).
        model_alias: One of 'gemini-lite' (default — gemini-3.5-flash-lite,
            cheapest, fastest), 'gemini-flash' (gemini-4-hydrogen, for images
            that need interpreting, ~8x cost), 'gemini-3.5-flash' (old name for
            'gemini-flash'), 'haiku' (Anthropic single-vendor option, weak
            prompt-following on dense transcription), 'opus' (Anthropic,
            interactive use). Unrecognized aliases default to 'gemini-lite' to
            avoid surprise costs.
        max_tokens: Response cap. Bumped from 1000 → 4000 because dense
            screenshots need it; the lowest Gemini thinking level keeps cost
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
