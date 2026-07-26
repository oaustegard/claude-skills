# mapping-webapp - Changelog

All notable changes to the `mapping-webapp` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.0] - 2026-03-24

### Other

- Rename mapping-features to mapping-webapp for accuracy

## [0.2.0] - 2026-03-22

### Added

- routes flag, incremental descriptions, redirect gating, proxy API

## [0.1.0] - 2026-03-22

### Added

- add mapping-webapp skill for behavioral web app documentation (#432)
## 0.4.0 — 2026-07-26

- Structure now comes from tree-sitting at runtime instead of committed `_MAP.md`
  files (mapping-codebases is deprecated). New `scripts/codecontext.py` wraps the
  scan; `analyze.py`, `describe.py`, `discover.py`, and `featuremap.py` delegate to it.
- `featuremap.py` no longer aborts when `_MAP.md` is absent; it checks that
  tree-sitting is installed instead.
- Page discovery reads the scanned file list directly rather than regex-scraping
  HTML references out of a root `_MAP.md`.
