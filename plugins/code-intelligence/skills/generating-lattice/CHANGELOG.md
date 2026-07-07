# Changelog

## 0.3.0 (2026-03-29)

- `suggest_backlinks.py`: Replaced regex-based symbol lookup with `_MAP.md`
  parsing for O(1) line number resolution. No more language-specific
  `SYMBOL_PATTERNS` dict. Requires `_MAP.md` files from mapping-codebases. (#505)
- New `annotate_maps.py`: Post-processor that adds `> Documented in:` lines to
  `_MAP.md` file headers, linking to lat.md sections via `@lat:` comments in
  source. Completes the three-layer navigation graph (maps ↔ lattice ↔ source).
  Idempotent. (#506)
- SKILL.md: Added Phase 4b documenting the annotate_maps step.

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

## [0.3.0] - 2026-03-30

### Other

- Lattice ↔ map integration: _MAP.md symbol lookup + cross-references (#509)

## [0.2.0] - 2026-03-29

### Added

- v0.2.0 — bidirectional anchoring as core mechanism (#497)