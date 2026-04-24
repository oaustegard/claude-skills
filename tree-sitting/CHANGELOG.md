# tree-sitting - Changelog

All notable changes to the `tree-sitting` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.5.0] - 2026-04-23

### Fixed

- Drop `tree-sitter-language-pack` dependency (#572). The 1.6.x wheels install into `_native/` with no top-level package directory, making imports fail in Claude.ai containers. Even if the import is patched, the pack tries to download grammars at runtime from a domain outside the network allowlist. Grammars are now loaded directly from bundled `parsers/*.so` via `ctypes`, against the bare `tree-sitter` package (which installs cleanly). Setup is simpler (no venv) and install is ~1s.

### Changed

- Setup command is now `uv pip install --system --break-system-packages tree-sitter` — no venv required.
- Supported-languages list narrowed to the 11 bundled grammars (Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java, C, HTML, Markdown). Previously advertised languages without bundled parsers silently returned empty before this change anyway; now they're documented honestly with instructions for adding a grammar.

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