# developing-preact - Changelog

All notable changes to the `developing-preact` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.2.1] - 2026-09-09

### Added

- add mapping-features skill for behavioral web app documentation (#432)

### Fixed

- repair broken frontmatter, mark obsolete skills, close registry gaps (#746)

### Other

- prompt-audit: dated prompting patterns across the skill catalogue (#791)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
- Add SessionStart hook for automatic Muninn boot

## [1.2.0] - 2026-03-08

### Added

- replace esm.sh CDN with vendored deps + container testing
- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Fixed

- limit markdown ToC to h1/h2 headings only