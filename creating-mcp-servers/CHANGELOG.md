# creating-mcp-servers - Changelog

All notable changes to the `creating-mcp-servers` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.2.0] - 2026-09-09

### Added

- add mapping-features skill for behavioral web app documentation (#432)
- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Fixed

- repair broken frontmatter, mark obsolete skills, close registry gaps (#746)
- limit markdown ToC to h1/h2 headings only

### Other

- prompt-audit: dated prompting patterns across the skill catalogue (#791)
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
