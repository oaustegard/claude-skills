---
name: transcribing-images
description: "Reads the visual content of slides, pages, and images the way a human would, not just their embedded text. Use when a PPTX or PDF has image slides, screenshots, charts, scanned figures, or flattened-to-image layouts that the built-in pptx/pdf skills read as empty; when asked to transcribe, describe, OCR, or extract what is shown in an image, slide deck, or document page; or when embedded-text extraction returned little or nothing from a visually rich file. Triggers on 'read this deck', 'what's on these slides', 'transcribe', 'OCR', 'extract text from image', 'describe this chart/diagram', .pptx/.pdf/.png/.jpg with visual content."
metadata:
  version: 0.1.0
---

# Transcribing Images

Read what a slide, page, or image actually *shows* — text plus charts,
diagrams, screenshots, and layout — by rasterizing it and sending the picture
to a vision model. This is the fix for the gap the built-in `pptx` and `pdf`
skills leave: they extract embedded text only, so an image slide, a chart, or a
scanned figure reads as empty. Visual transcription reads it the way a person
looking at the slide would.

## When to reach for this vs. the built-in skills

Use the `pptx` / `pdf` skills first for **text-native** documents — a normal
deck or report where the content is real text boxes. They are faster and exact.

Switch to this skill when text extraction comes back thin or empty on a file
you can see is visually rich, or whenever the meaningful content is a **picture**:
chart, graph, diagram, screenshot, photo, scanned page, or a slide exported as
one flat image. Don't guess which case you're in — if `pptx`/`pdf` returned
little from a file that clearly has content, that *is* the signal.

## The pipeline

Everything routes through `scripts/transcribe_pages.py`, which handles all
three ingress paths and one bad page never aborts the rest:

- `.pptx` / `.ppt` → LibreOffice headless → PDF → `pdftoppm` → one PNG per slide
- `.pdf` → `pdftoppm` → one PNG per page
- image file → used directly as a single page

Each page image is then transcribed by a vision model. Run it directly:

```bash
python3 scripts/transcribe_pages.py deck.pptx                  # all slides
python3 scripts/transcribe_pages.py report.pdf --pages 3-7     # subset
python3 scripts/transcribe_pages.py slide.png --model opus     # one image
python3 scripts/transcribe_pages.py deck.pptx --json out.json  # structured
```

Or import `transcribe_file(...)` for programmatic use; it returns a list of
`{page, image, text, error}` dicts.

## Choosing the model

The transcription core and its empirical cost/recall data are reused from
`browsing-bluesky/scripts/image_transcribe.py` — same registry, kept in sync.
Pick with `--model`:

- `gemini-lite` (default) — cheapest and fastest, ~95% token recall on dense
  screenshots. Right for routine deck reading.
- `gemini-flash` — token-perfect, ~3x the cost. Use when exact text matters.
- `gemini-3.5-flash` — frontier reasoning alongside transcription, ~19x cost.
  Use when a page needs interpretation, not just reading.
- `opus` — for interactive sessions where you want the reading in your own
  context anyway.
- `haiku` — only if constrained to single-vendor Anthropic; weak at dense
  transcription (tends to summarize instead of transcribe).

Default to `gemini-lite` and escalate only when recall or reasoning demands it.

## OCR fallback (tesseract)

Tesseract 5.x is installed (`eng` + `osd` language packs only) and is exposed
as `--engine tesseract`. It returns **glyphs, not a reading** — no chart
interpretation, no diagram description, no layout meaning. Use it only for
pages you already know are plain scanned text, when you want a zero-cost,
fully-offline pass. For anything with a chart, diagram, or visual layout, the
vision path is the correct tool; tesseract on those pages will quietly lose the
content that mattered.

## Interactive shortcut

In an interactive session you can often skip the model call entirely:
rasterize with `scripts/transcribe_pages.py … --json` to get the page PNGs, or
just convert and `view` each page image yourself — Claude reads images natively.
The script's vision-model path exists for batch and autonomous runs where no
human-in-loop reader is available, or when a deck has more pages than is
practical to view one by one.

## DPI

Default raster is 150 DPI — legible for a vision model and safely under the
5 MB/image base64 ceiling. Bump to `--dpi 200`–`300` only for pages with dense
small fonts; higher DPI risks exceeding the per-image size limit and costs more
tokens for no gain on normal slides.
