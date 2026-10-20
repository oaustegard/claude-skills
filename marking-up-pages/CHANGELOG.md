# marking-up-pages - Changelog

All notable changes to the `marking-up-pages` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-10-20

### Other

- marking-up-pages 0.2.0: Copy and Save for standalone (bookmarklet) use

## [0.2.0] - 2026-10-20

### Added

- Standalone export: **Copy** (summary text to clipboard, with an `execCommand` fallback) and **Save** (downloads `<host>-<date>-<time>.scrawl.json` with `export({ points: true })` plus `summary` and `saved`) on the toolbar, and `__scrawl.copy()` / `__scrawl.save()`. The bookmarklet previously had no way to get marks off the page without Claude in Chrome.

## [0.1.0] - 2026-10-20

### Other

- marking-up-pages 0.1.0: draw on a live page, hand marks to Claude in Chrome