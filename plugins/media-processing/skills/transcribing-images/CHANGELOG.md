# transcribing-images - Changelog

All notable changes to the `transcribing-images` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-10-07

### Changed

- Fallback model registry in `transcribe_pages.py` moved to `claude-haiku-5-5` (was
  `claude-haiku-4-5-20251001`) and `claude-opus-5-5` (was `claude-opus-4-7`), matching
  `browsing-bluesky/scripts/image_transcribe.py`. Adaptive thinking on these models
  counts against `--max-tokens` (default 4000); raise it if a page comes back empty.

## [0.1.2] - 2026-09-12

### Other

- Add ocring-pdfs skill; route file-deliverable OCR out of transcribing-images (#796)

## [0.1.2] - 2026-09-12

### Changed

- Route file-deliverable OCR to the new `ocring-pdfs` skill; the tesseract
  engine here stays for loose-text passes on pages already known to be plain
  scans.

## [0.1.1] - 2026-09-09

### Other

- prompt-audit: dated prompting patterns across the skill catalogue (#791)
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)

## [0.1.0] - 2026-06-19

### Added

- transcribing-images skill (visual reading of slides/pages) (#703)