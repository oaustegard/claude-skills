# creating-video - Changelog

All notable changes to the `creating-video` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.1] - 2026-07-22

### Fixed

- --keep-audio was a no-op — port audio crossfade from the stale branch (#742)

## [0.2.1] - 2026-07-21

### Fixed

- `assemble.py`: `--keep-audio` was a no-op — trimmed clips kept audio but the
  stitch stage mapped only video, so the flag silently produced a silent film.
  Adds the `acrossfade` chain, `afade` out, and explicit `[k:v]`/`[k:a]` stream
  specifiers; pads the held tail with `apad` so A/V stay equal length.

## [0.2.0] - 2026-07-21

### Other

- creating-video: default to Gemini Omni Flash (#739)

## [0.1.0] - 2026-07-18

### Other

- Add creating-video skill; extend parsing-video for editing review (#735)