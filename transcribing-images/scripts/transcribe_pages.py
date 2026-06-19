#!/usr/bin/env python3
"""Rasterize PPTX / PDF / image files to page images and transcribe each one.

WHY THIS EXISTS
---------------
The built-in pptx and pdf skills read *embedded text only*. A slide whose
content is a screenshot, chart, scanned figure, or flattened-to-image layout
reads as empty or near-empty — the exact failure that motivated this skill.
The fix is to treat every page as a picture: rasterize it, then send the
raster to a vision model that reads it the way a human looking at the slide
would. Embedded-text extraction is the wrong tool for image slides; visual
transcription is the right one.

INGRESS PATHS
-------------
  .pptx / .ppt  -> LibreOffice headless -> PDF -> pdftoppm -> one PNG / page
  .pdf          -> pdftoppm -> one PNG / page
  image file    -> used directly (single "page")

The transcription core (model registry, Pareto cost data, graceful-degradation
policy) is REUSED from browsing-bluesky/scripts/image_transcribe.py rather than
duplicated. That module only accepts a URL; this one adds a local-path / bytes
entry point and the rasterization front-end on top of the same routing.

OCR FALLBACK
------------
Tesseract is available (eng + osd only) and is the cheap path for a page that
is purely scanned text with no diagram/chart/layout meaning. It is NOT a
substitute for visual transcription: it returns glyphs, not a reading. Use
`engine='tesseract'` only when you know the page is plain text and you want a
zero-cost, offline pass. Default is a vision model.

CLI
---
    python3 transcribe_pages.py deck.pptx                 # all pages, gemini-lite
    python3 transcribe_pages.py report.pdf --pages 3-7    # page subset
    python3 transcribe_pages.py slide.png --model opus     # single image
    python3 transcribe_pages.py scan.pdf --engine tesseract  # offline OCR
    python3 transcribe_pages.py deck.pptx --dpi 200 --json out.json

Returns / prints one transcription block per page. On any per-page failure the
block records the error and processing continues — one bad page never aborts
the deck.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Reuse the transcription routing core from the bsky skill. It carries the
# model registry and the empirical cost/recall Pareto data; don't re-derive it.
_TRANSCRIBE_CORE = "/mnt/skills/user/browsing-bluesky/scripts"
_GEMINI_CLIENT_PATH = "/mnt/skills/user/invoking-gemini/scripts"
_CLAUDE_CLIENT_PATH = "/mnt/skills/user/orchestrating-agents/scripts"

_MAX_BYTES = 5 * 1024 * 1024  # Anthropic / Gemini per-image base64 ceiling.

_SUFFIX_BY_CTYPE = {
    "image/png": ".png", "image/jpeg": ".jpg",
    "image/webp": ".webp", "image/gif": ".gif",
}
_CTYPE_BY_SUFFIX = {v: k for k, v in _SUFFIX_BY_CTYPE.items()}
_CTYPE_BY_SUFFIX[".jpeg"] = "image/jpeg"

# Page transcription prompt — broader than the bsky one. Slides carry charts,
# diagrams, and layout meaning, not just text glyphs, so ask for both the text
# AND a concrete reading of any non-text visual.
_PAGE_PROMPT = (
    "Transcribe this slide/page as a human reader would understand it. "
    "Extract ALL text verbatim (titles, body, labels, captions, footnotes, "
    "table cells) preserving reading order and structure. For every non-text "
    "visual — chart, graph, diagram, photo, screenshot, icon — describe what "
    "it shows concretely: chart type, axes, trend direction, what is being "
    "compared, what the diagram connects. State numbers and data points you "
    "can read off charts. If the page is a single full-bleed image, describe "
    "it in full. Do not editorialize or summarize away detail. Output as "
    "structured markdown."
)


# ──────────────────────────────────────────────────────────────────────────
# Rasterization front-end
# ──────────────────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def pptx_to_pdf(pptx_path: str, out_dir: str) -> Optional[str]:
    """Convert PPTX/PPT to PDF via LibreOffice headless. Returns PDF path."""
    rc, _, err = _run([
        "libreoffice", "--headless", "--convert-to", "pdf",
        "--outdir", out_dir, pptx_path,
    ], timeout=180)
    if rc != 0:
        sys.stderr.write(f"[pptx_to_pdf] libreoffice rc={rc}: {err[:300]}\n")
        return None
    stem = Path(pptx_path).stem
    pdf = os.path.join(out_dir, stem + ".pdf")
    return pdf if os.path.exists(pdf) else None


def pdf_to_pngs(pdf_path: str, out_dir: str, dpi: int = 150,
                first: Optional[int] = None, last: Optional[int] = None) -> list[str]:
    """Rasterize PDF pages to PNGs via pdftoppm. Returns sorted PNG paths.

    150 dpi is the default: legible for a vision model without blowing the
    5 MB/image base64 ceiling. Bump to 200-300 only for dense small-font pages.
    """
    prefix = os.path.join(out_dir, "page")
    cmd = ["pdftoppm", "-png", "-r", str(dpi)]
    if first is not None:
        cmd += ["-f", str(first)]
    if last is not None:
        cmd += ["-l", str(last)]
    cmd += [pdf_path, prefix]
    rc, _, err = _run(cmd, timeout=180)
    if rc != 0:
        sys.stderr.write(f"[pdf_to_pngs] pdftoppm rc={rc}: {err[:300]}\n")
        return []
    return sorted(str(p) for p in Path(out_dir).glob("page*.png"))


def rasterize(src: str, out_dir: str, dpi: int = 150,
              first: Optional[int] = None, last: Optional[int] = None) -> list[str]:
    """Turn any supported source into a list of page-image paths."""
    ext = Path(src).suffix.lower()
    if ext in (".pptx", ".ppt"):
        pdf = pptx_to_pdf(src, out_dir)
        if not pdf:
            return []
        return pdf_to_pngs(pdf, out_dir, dpi=dpi, first=first, last=last)
    if ext == ".pdf":
        return pdf_to_pngs(src, out_dir, dpi=dpi, first=first, last=last)
    if ext in _CTYPE_BY_SUFFIX:
        return [src]  # already an image; single page
    sys.stderr.write(f"[rasterize] unsupported extension: {ext}\n")
    return []


# ──────────────────────────────────────────────────────────────────────────
# Transcription: vision-model path (reused core) + tesseract fallback
# ──────────────────────────────────────────────────────────────────────────

def _read_local(path: str) -> Optional[tuple[bytes, str]]:
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        sys.stderr.write(f"[_read_local] {e}\n")
        return None
    if len(data) > _MAX_BYTES:
        sys.stderr.write(f"[_read_local] {path} exceeds 5 MB; downscale first\n")
        return None
    ctype = _CTYPE_BY_SUFFIX.get(Path(path).suffix.lower(), "image/png")
    return data, ctype


def _transcribe_vision(path: str, model_alias: str, max_tokens: int,
                       prompt: str) -> Optional[str]:
    """Vision-model transcription of a LOCAL image.

    Mirrors image_transcribe.py's backend dispatch but feeds local bytes
    instead of a downloaded URL. The model registry itself is imported from
    that module so the two stay in sync.
    """
    if _TRANSCRIBE_CORE not in sys.path:
        sys.path.insert(0, _TRANSCRIBE_CORE)
    try:
        from image_transcribe import _MODEL_REGISTRY
    except ImportError:
        # Fallback registry if the bsky skill isn't present in this env.
        _MODEL_REGISTRY = {
            "haiku": ("anthropic", "claude-haiku-4-5-20251001"),
            "opus": ("anthropic", "claude-opus-4-7"),
            "gemini-lite": ("gemini", "gemini-2.5-flash-lite"),
            "gemini-flash": ("gemini", "gemini-2.5-flash"),
            "gemini-3.5-flash": ("gemini", "gemini-3.5-flash"),
        }
    backend, model = _MODEL_REGISTRY.get(model_alias, _MODEL_REGISTRY["gemini-lite"])

    fetched = _read_local(path)
    if fetched is None:
        return None
    data, ctype = fetched

    if backend == "gemini":
        if _GEMINI_CLIENT_PATH not in sys.path:
            sys.path.insert(0, _GEMINI_CLIENT_PATH)
        try:
            from gemini_client import invoke_gemini
        except ImportError:
            return None
        try:
            out = invoke_gemini(prompt=prompt, model=model, image_path=path,
                                max_output_tokens=max_tokens,
                                thinking_level="minimal")
            return out.strip() if out else None
        except Exception as e:
            sys.stderr.write(f"[_transcribe_vision gemini] {e}\n")
            return None

    if backend == "anthropic":
        if _CLAUDE_CLIENT_PATH not in sys.path:
            sys.path.insert(0, _CLAUDE_CLIENT_PATH)
        try:
            from claude_client import invoke_claude
        except ImportError:
            return None
        b64 = base64.standard_b64encode(data).decode("ascii")
        content = [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": ctype, "data": b64}},
            {"type": "text", "text": prompt},
        ]
        try:
            return invoke_claude(content, model=model, max_tokens=max_tokens).strip()
        except Exception as e:
            sys.stderr.write(f"[_transcribe_vision anthropic] {e}\n")
            return None
    return None


def _transcribe_tesseract(path: str) -> Optional[str]:
    """Offline OCR fallback. Glyphs only — no diagram/chart reading.

    Use only for pages known to be plain scanned text. eng + osd are the only
    installed language packs.
    """
    try:
        rc, out, err = _run(["tesseract", path, "stdout", "-l", "eng"], timeout=60)
        if rc != 0:
            sys.stderr.write(f"[tesseract] rc={rc}: {err[:200]}\n")
            return None
        return out.strip() or None
    except Exception as e:
        sys.stderr.write(f"[tesseract] {e}\n")
        return None


# ──────────────────────────────────────────────────────────────────────────
# Orchestration
# ──────────────────────────────────────────────────────────────────────────

def transcribe_file(src: str, model_alias: str = "gemini-lite",
                    engine: str = "vision", dpi: int = 150,
                    first: Optional[int] = None, last: Optional[int] = None,
                    max_tokens: int = 4000,
                    prompt: str = _PAGE_PROMPT) -> list[dict]:
    """Rasterize `src` and transcribe each page.

    engine: 'vision' (default; model_alias selects the model) or 'tesseract'
            (offline OCR, glyphs only). One bad page logs an error and
            continues — never aborts the whole file.

    Returns a list of {page, image, text, error} dicts, one per page.
    """
    with tempfile.TemporaryDirectory() as tmp:
        pages = rasterize(src, tmp, dpi=dpi, first=first, last=last)
        if not pages:
            return [{"page": 0, "image": None, "text": None,
                     "error": f"rasterization produced no pages for {src}"}]

        results = []
        # pdftoppm numbers from the absolute page; reflect `first` offset.
        base = first or 1
        for i, img in enumerate(pages):
            page_no = base + i
            if engine == "tesseract":
                text = _transcribe_tesseract(img)
            else:
                text = _transcribe_vision(img, model_alias, max_tokens, prompt)
            results.append({
                "page": page_no,
                "image": os.path.basename(img),
                "text": text,
                "error": None if text else "transcription returned None",
            })
        return results


def _parse_pages(spec: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    if not spec:
        return None, None
    if "-" in spec:
        a, b = spec.split("-", 1)
        return int(a), int(b)
    n = int(spec)
    return n, n


def main():
    ap = argparse.ArgumentParser(description="Transcribe PPTX/PDF/image pages via a vision model.")
    ap.add_argument("src", help="Path to .pptx/.ppt/.pdf/image file")
    ap.add_argument("--model", default="gemini-lite",
                    help="gemini-lite (default), gemini-flash, gemini-3.5-flash, haiku, opus")
    ap.add_argument("--engine", default="vision", choices=["vision", "tesseract"],
                    help="vision (default) or tesseract (offline OCR, plain text only)")
    ap.add_argument("--pages", default=None, help="page or range, e.g. 3 or 3-7")
    ap.add_argument("--dpi", type=int, default=150, help="raster DPI (default 150)")
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--json", default=None, help="write results to this JSON path")
    args = ap.parse_args()

    first, last = _parse_pages(args.pages)
    results = transcribe_file(
        args.src, model_alias=args.model, engine=args.engine,
        dpi=args.dpi, first=first, last=last, max_tokens=args.max_tokens,
    )

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
        ok = sum(1 for r in results if r["text"])
        print(f"Wrote {len(results)} pages ({ok} transcribed) to {args.json}")
    else:
        for r in results:
            print(f"\n{'=' * 70}\nPAGE {r['page']}  ({r['image']})\n{'=' * 70}")
            print(r["text"] if r["text"] else f"[error: {r['error']}]")


if __name__ == "__main__":
    main()
