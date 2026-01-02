# mapping-codebases - Changelog

All notable changes to the `mapping-codebases` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.4.0] - 2026-01-02

### Added

- Update mapping-codebases to v0.4.0 with uv and CLAUDE.md integration

### Fixed

- Correct ephemeral environment instructions for map persistence

## [0.4.0] - 2026-01-02

### Added

- **Post-generation CLAUDE.md integration**: After generating `_MAP.md` files, Claude now updates or creates the repository's CLAUDE.md to document map usage and maintenance
- **Environment-aware workflow**: Distinguishes between Claude Code (persistent repos) and Claude.ai chat (ephemeral) to provide appropriate guidance
- **Map persistence documentation**: Instructions for keeping maps fresh and avoiding drift from source code

### Changed

- **Installation instructions**: Explicitly prioritize `uv pip install --system` for Claude Code environments over pip
- **Improved guidance**: Added "CRITICAL" markers for key instructions to ensure Claude follows best practices

### Fixed

- Claude Code now uses `uv` by default instead of attempting `pip` first (addresses user feedback from third-party testing)
- Ephemeral environment instructions now correctly tell users to invoke the skill (to regenerate maps) rather than assuming _MAP.md files persist

## [0.3.0] - 2026-01-02

### Added

- Update mapping-codebases to v0.3.0 with hierarchy support
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Changed

- Update to tree-sitter-language-pack and uv

### Other

- Merge PR #160 changes with tree-sitter-language-pack updates
- Improve codemap.py with symbol hierarchy and add comparison with Serena