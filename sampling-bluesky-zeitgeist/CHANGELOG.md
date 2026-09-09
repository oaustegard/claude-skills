# sampling-bluesky-zeitgeist - Changelog

All notable changes to the `sampling-bluesky-zeitgeist` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.1] - 2026-09-09

### Added

- add mapping-features skill for behavioral web app documentation (#432)
- add trending API and fix NODE_PATH resolution (#271, #272)
- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance
- Consolidate firehose sampling into browsing-bluesky
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Fixed

- limit markdown ToC to h1/h2 headings only

### Other

- prompt-audit: dated prompting patterns across the skill catalogue (#791)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
- Mark skill as deprecated and link to browsing-bluesky
