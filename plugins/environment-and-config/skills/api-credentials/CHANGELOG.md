# api-credentials - Changelog

All notable changes to the `api-credentials` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.0.4] - 2026-10-11

### Added

- add mapping-features skill for behavioral web app documentation (#432)
- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Changed

- use configuring skill for TURSO_URL with protocol-agnostic config
- migrate API credential management to project knowledge files

### Fixed

- limit markdown ToC to h1/h2 headings only

### Other

- orchestrating-agents renamed orchestrating-chat-agents; old name deprecated
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
- Update README.md
