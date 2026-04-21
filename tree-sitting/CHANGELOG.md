# tree-sitting - Changelog

All notable changes to the `tree-sitting` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.4.0] - 2026-04-21

### Other

- tree-sitting: show line ranges in sparse/normal tree overviews (#568)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)

## [0.4.0] - 2026-04-21

### Added

- Tree overview now shows `:start-end` line ranges per symbol in `sparse` and `normal` detail levels, not just `full`. The default orientation output (used by `exploring-codebases` step 2) becomes actionable: pick a symbol's line window and feed it directly to `Read` via `offset`/`limit` without a second treesit call.

## [0.3.0] - 2026-04-08

### Added

- add treesit.py CLI, fix cross-process cache loss, fix Symbol dict bug (#536)

### Other

- marketplace: restructure as category-based plugins for Claude Code discovery (#530)
- Add missing READMEs for searching-codebases, featuring, tree-sitting (#521)

## [0.2.0] - 2026-03-31

### Added

- tree-sitting v0.2.0 — AST navigation + tags.scm extraction (#511)