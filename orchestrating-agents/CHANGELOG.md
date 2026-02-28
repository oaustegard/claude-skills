# orchestrating-agents - Changelog

All notable changes to the `orchestrating-agents` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-02-28

### Added

- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Changed

- migrate API credential management to project knowledge files

### Fixed

- resolve issues #311 and #312 in claude_client.py
- limit markdown ToC to h1/h2 headings only

### Other

- Update subagent models: default to Sonnet 4.6, add Haiku 4.5 support
