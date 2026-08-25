# creating-skill - Changelog

All notable changes to the `creating-skill` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.3.0] - 2026-08-25

### Other

- top skills: separate by omission, and correct the guidance that said otherwise (#777)
- creating-skill: use Anthropic's quick_validate.py instead of a hand-rolled check (#775)

## [2.2.0] - 2026-08-25

### Added

- add mapping-features skill for behavioral web app documentation (#432)
- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Changed

- simplify creating-skill and align with CI principles

### Fixed

- repair broken frontmatter, mark obsolete skills, close registry gaps (#746)
- limit markdown ToC to h1/h2 headings only

### Other

- Applicability boundaries, real failure signals, findable descriptions (#774)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)