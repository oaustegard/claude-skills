# tiling-tree - Changelog

All notable changes to the `tiling-tree` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.1.0] - 2026-10-07

### Added

- add mapping-features skill for behavioral web app documentation (#432)
- dynamic boot, read_file tool, dispatch mode, all-tools-all-modes (#333)

### Other

- Migrate hardcoded model defaults to the 5.5 generation
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
- Regenerate _MAP.md files after @lat: backlink insertion (#504)
- Lattice v2: bidirectional source-anchored knowledge graph (#503)

## [1.1.0] - 2026-10-07

### Changed

- Splitter and evaluator calls use `claude-sonnet-5-5` (was `claude-sonnet-4-6`). The
  evaluator's `temperature=0.8` is now dropped by `claude_client` on this model, which
  rejects non-default sampling parameters.

## [1.0.1] - 2026-03-06

### Fixed

- remove shim and local _parse_json workarounds from tiling-tree (#314)
- resolve issues #311 and #312 in claude_client.py

### Other

- Update subagent models: default to Sonnet 4.6, add Haiku 4.5 support