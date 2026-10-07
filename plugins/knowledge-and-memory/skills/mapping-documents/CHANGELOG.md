# mapping-documents - Changelog

## [0.2.0] - 2026-10-07

### Other

- Migrate hardcoded model defaults to the 5.5 generation

## [0.2.0] - 2026-10-07

### Changed

- Default model `claude-sonnet-4-6` -> `claude-sonnet-5-5` (`docmap.py`, SKILL.md).

### Fixed

- `_semantic_extract` joins the response's `text` blocks instead of reading
  `content[0].text`, which failed on adaptive-thinking models that lead with an empty
  `thinking` block.

## [0.1.2] - 2026-04-17

### Added

- Add/Update skill: mapping-documents (#551)

## [0.1.2] - 2026-04-17

### Added
- README.md with consumption model, three-layer stack diagram, example output, quick start

### Changed
- Version bump across SKILL.md, docmap.py usage snippet template

## [0.1.1] - 2026-04-17

### Added
- `_USAGE.md` output: snippet for pasting into CLAUDE.md / AGENTS.md / project instructions
- Three-layer progressive-disclosure stack documentation in SKILL.md
- JSON query examples for symbols and anchors
- `--no-usage-snippet` CLI flag

### Changed
- SKILL.md rewritten with "After Generating: Wire It Up" section

## [0.1.0] - 2026-04-17

### Added
- Initial release: font-based structural parsing, parallel LLM semantic extraction
- Genre support: paper, spec, legal
- Outputs: _MAP.md, .symbols.json, .anchors.json
## 0.1.3 — 2026-07-26

- Repointed the structural-analogy reference from mapping-codebases (deprecated) to
  tree-sitting. This skill's own `{stem}_MAP.md` document maps are unchanged.