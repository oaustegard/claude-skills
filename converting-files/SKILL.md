---
name: converting-files
description: Convert a file from one format to another inside the container — documents, images, audio, video. Routes to the right engine (pandoc, LibreOffice, ImageMagick, ffmpeg) by format pair. Triggers on "convert X to Y", "turn this docx into a pdf", "make a gif from this mp4", "md to docx", "batch-convert these images", or any single-file or batch format change where the source and target extensions differ. NOT for editing content (use docx/pptx/xlsx/pdf skills), creating files from scratch, or reading a file you already have in context.
metadata:
  version: 0.1.0
---

# converting-files

Four conversion engines are already in this container — `pandoc`, `libreoffice`
(headless), ImageMagick's `convert`, and `ffmpeg`. The hard part isn't running
them; it's picking the right one. pandoc mangles a real `.docx` into PDF;
LibreOffice is the tool for that. pandoc is *better* than LibreOffice for
`md → docx`. Neither touches `mp4 → gif`. This skill encodes that routing so the
choice isn't re-derived (often wrongly) each time.

`scripts/convert.py` is a dispatcher over those four binaries, not a new engine.
Use it for the common cases; drop to the raw engine when you need flags it
doesn't pass through.

## Is this the right skill?

| You want to… | Use instead |
| --- | --- |
| Change a file's **format** (ext A → ext B) | **this skill** |
| Edit/author a Word/PPT/Excel/PDF's **content** | `docx` / `pptx` / `xlsx` / `pdf` skills |
| Read a file already shown in context | just read it — no conversion |
| Extract text/tables *from* a PDF | `pdf-reading` skill |
| Fill or merge PDFs | `pdf` skill |

Format change = here. Content change = a content skill. A `docx → pdf` is a
format change; "fix the grammar in this docx" is not.

## Engine routing (the actual content of this skill)

Source family → target family decides the engine. The dispatcher applies this;
the table is here so the reasoning is auditable and so you can call the engine
directly when needed.

| From → To | Engine | Why |
| --- | --- | --- |
| markup → markup (md, html, rst, latex, org, epub, rtf, ipynb…) | **pandoc** | what it's built for |
| markup → Office (md → docx/pptx/odt) | **pandoc** | cleaner than LibreOffice from markup |
| Office → markup (docx/odt/pptx → md/html…) | **pandoc** | reads modern OOXML well |
| **Office → PDF** (docx/pptx/xlsx → pdf) | **LibreOffice** | preserves layout; pandoc mangles it |
| Office ↔ Office, or **legacy** (.doc/.ppt/.xls) anything | **LibreOffice** | pandoc can't read legacy binary formats at all |
| markup → PDF (md → pdf) | **pandoc** (+pdflatex/xelatex) | lighter than LibreOffice for plain markup |
| image ↔ image (png, jpg, gif, webp, tiff, heic, svg…) | **ImageMagick** | `convert in out` |
| image → PDF | **ImageMagick** | |
| audio ↔ audio (mp3, wav, flac, ogg, aac, m4a, opus…) | **ffmpeg** | |
| video ↔ video, **mp4 → gif**, gif → mp4 | **ffmpeg** | gif-from-video is an ffmpeg job, not ImageMagick |

`gif` lives in both image and video worlds: `png → gif` is ImageMagick (still
image), `mp4 → gif` is ffmpeg (animation). The dispatcher handles the split by
the *source* family.

## Usage

```bash
# Plan only — print engine + reason + exact command, run nothing. Do this first
# on an unfamiliar pair to confirm the route before committing.
python3 /mnt/skills/user/converting-files/scripts/convert.py --plan in.docx out.pdf

# Convert.
python3 /mnt/skills/user/converting-files/scripts/convert.py in.docx out.pdf
python3 /mnt/skills/user/converting-files/scripts/convert.py notes.md notes.docx
python3 /mnt/skills/user/converting-files/scripts/convert.py clip.mp4 clip.gif

# Pass engine flags through (everything after OUTPUT goes to the engine):
python3 .../convert.py photo.png photo.jpg -quality 85         # ImageMagick
python3 .../convert.py song.wav song.mp3 -b:a 192k             # ffmpeg
python3 .../convert.py paper.md paper.pdf --pdf-engine=xelatex # pandoc

# Force a specific engine if you disagree with the route:
python3 .../convert.py weird.docx weird.md --engine pandoc
```

Exit codes: `0` ok, `2` no route exists, `3` engine failed (stderr tail
printed), `4` bad args / missing input.

## Batch

The dispatcher is one file at a time by design — batch is a shell loop so each
file's failure is visible:

```bash
for f in *.png; do
  python3 /mnt/skills/user/converting-files/scripts/convert.py "$f" "${f%.png}.webp" || echo "FAILED: $f"
done
```

## Gotchas (the things that cost a re-run)

- **LibreOffice names the output itself** — it writes `<input-stem>.<ext>` into
  `--outdir`, ignoring your chosen filename. The dispatcher renames to your
  `OUTPUT` after. If you call `libreoffice` raw, expect the input-stem name.
- **LibreOffice headless is single-instance.** Two concurrent `--headless` calls
  collide on the user profile and one silently does nothing. Run them serially
  (the batch loop above is serial — fine).
- **markup → pdf needs a LaTeX engine.** `pdflatex`/`xelatex` are present, but
  exotic Unicode wants `--pdf-engine=xelatex`. If LaTeX chokes on the content,
  route through `docx` first: `md → docx` (pandoc) then `docx → pdf` (LibreOffice).
- **ImageMagick here is IM6** (`convert`, not `magick`). Policy may block some
  formats; if `convert` refuses a PDF/PS op, that's the `/etc/ImageMagick-6/policy.xml`
  security policy, not a missing codec.
- **markup → jira emits heading anchors.** `md → jira` works (both are pandoc
  formats), but headings come out as `h1. {anchor:slug}Title` — pandoc materializing
  the auto-generated heading ID. Suppress with
  `--engine pandoc ... -f markdown-auto_identifiers` (pass the format-with-extension
  yourself, since the dispatcher infers a bare `markdown`).
- **`--plan` lies about nothing but runs nothing** — it can't tell you the
  *content* will survive (e.g. a pptx → md drops all layout). Plan checks the
  route; only a real run checks the result.

## Why not VERT (or any web converter) as the skill

VERT (vert.sh) is a Svelte/WASM **browser app** wrapping these same engines
(libvips, ffmpeg.wasm, Pandoc-wasm) for a human at a tab who wants local privacy.
There's no library or CLI to import — the app *is* the UI. In-container we
already have the native binaries with full filesystem access and no browser
memory ceiling, so the WASM wrappers would be strictly slower and weaker. VERT is
a good *recommendation to a person*; it's the wrong shape for a skill. This skill
is the in-container equivalent of what VERT does in a tab.
