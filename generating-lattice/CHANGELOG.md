# Changelog

## 0.2.0 (2026-03-29)

- **Breaking**: Back-links (Phase 4) are no longer optional — they are the
  bottom-up half of drift detection
- Restructured pipeline: generation (Phase 3) now emphasizes source code
  anchoring as the primary output, not section-to-section links
- Added "Drift Prevention" section explaining how bidirectional linking enables
  `lat check` to catch documentation drift
- Moved agent integration to Phase 6 (after validation)
- Added anti-patterns section documenting v0.1 failures
- Added `require-code-mention` guidance for critical sections
- Quality criteria now requires all four `lat check` checks to pass

## 0.1.0 (2026-03-29)

- Initial release with mapping-codebases integration and lat.md generation
  pipeline

## [0.2.0] - 2026-03-29

### Added

- v0.2.0 — bidirectional anchoring as core mechanism (#497)
