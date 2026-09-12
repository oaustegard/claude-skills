---
name: ocring-pdfs
description: "Adds a searchable text layer to a scanned PDF with ocrmypdf. Installs the toolchain at runtime in ~18s. Use when a PDF's pages are images and the deliverable is a file to keep, grep, or hand to another tool: 'make this PDF searchable', 'OCR this scan', 'I can't select the text in this PDF', 'search across these scanned pages', 'the pdf skill returned nothing'. Handles non-English scans via tesseract language packs. NOT for charts, diagrams, handwriting, or slide layouts. Route those to transcribing-images."
metadata:
  version: 0.1.0
---

# OCRing PDFs

`ocrmypdf` writes an invisible text layer over the original page images, so the
output file is both the scan you can look at and a document `pdftotext`, `grep`,
and `pdfplumber` can read. Rasterize-then-tesseract gives you a `.txt` divorced
from the pages; page numbers and coordinates are gone.

The toolchain is not in the base container. It installs in 18 seconds
(measured 2026-09-12: apt 3s, pip 15s), so install it when a scan shows up
rather than carrying it in a container layer.

## Probe before installing

```bash
pdftotext in.pdf - | tr -d '\f \n' | wc -c
```

Nonzero means the PDF already has a text layer and is not a scan. Extract with
`pdftotext` or `pdfplumber` and stop. Running OCR on it wastes a minute, and with
`--force-ocr` it replaces exact embedded text with a lossy reading of a raster of
itself.

A small nonzero count (tens of characters across many pages) is the mixed case:
a born-digital cover page in front of scanned body pages, or a scan whose
producer stamped a header. `--skip-text` handles it.

## Install

```bash
sh scripts/ensure_ocr.sh              # English
sh scripts/ensure_ocr.sh nor deu      # plus Norwegian and German
```

Idempotent: 0.8s when everything is already present, 2.6s to add one more
language pack. Installs `ghostscript`, `pngquant`, `poppler-utils`, `tesseract`
and its language packs via apt, then `ocrmypdf` via pip.

## Run

```bash
ocrmypdf --skip-text --deskew --rotate-pages --output-type pdf in.pdf out.pdf
pdftotext out.pdf - | wc -w        # verify: zero words means it failed quietly
```

About 2s per page for a single dense page at 200 DPI on one core. A 300-page
scan is therefore a background job, not a single bash call — launch it detached
with a sentinel file per the external-call pattern in `bash-tool-timeout`.

## Which text-layer mode

| flag | use it when |
|---|---|
| `--skip-text` | Default. Pages that already carry text are passed through untouched; image-only pages get OCR. The safe choice for anything mixed. |
| `--force-ocr` | Every page is rasterized and re-OCRed, discarding any existing text. Correct for a scan carrying a junk text layer, and for pages with text-over-image that `--skip-text` would skip. Destroys real embedded text, so probe first. |
| `--redo-ocr` | Replaces a previous OCR layer while leaving born-digital text alone. Narrower than `--force-ocr` and slower to fail on odd inputs. |

`--output-type pdf` skips PDF/A conversion. Drop it when the output is going into
an archive that requires PDF/A; ghostscript does the conversion either way.

## Languages

`-l eng+nor` for a mixed-language document, `-l nor` for a monolingual one. Order
does not matter. Every code needs its `tesseract-ocr-<code>` pack installed.
Pass the codes to `ensure_ocr.sh` and it handles them. Accuracy drops noticeably
when the language is wrong, and tesseract will not tell you; it returns
confident garbage instead.

## Container facts (measured 2026-09-12)

- `apt-get update` exits 100 here. A preconfigured nodesource repo is off the
  egress allowlist and returns 403, and the nonzero exit aborts any `&&` chain
  behind it. The Ubuntu mirrors are reachable without an update. Run
  `apt-get install` directly.
- `unpaper` is absent, so `--clean` and `--clean-final` fail. Don't pass them.
- One core, so `--jobs` buys nothing on claude.ai. CCotw has four.
- `ocrmypdf --version` prints to stderr. Capture with `2>&1` or a version check
  reads as empty.
- `jbig2` is absent; output uses CCITT/JPEG instead, which costs some file size
  and nothing else.

## When to use transcribing-images instead

This skill produces glyphs. It does not read a chart, describe a diagram, or
recover handwriting. Tesseract on those pages returns nothing useful and gives no sign that it lost
anything.

Route to `transcribing-images` when the meaningful content is a picture, or when
the deliverable is a reading rather than a file. Both is a normal answer: OCR the
document so it is greppable, then send the pages that carry figures to a vision
model.

In an interactive session, native vision beats both for a handful of pages:
rasterize with `pdftoppm -r 200 -png` and `view` the images. Reach for OCR when
the document is longer than context will hold, or when the text has to outlive
the conversation as a file.
