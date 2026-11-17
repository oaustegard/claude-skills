# creating-skill - Changelog

All notable changes to the `creating-skill` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.6.0] - 2026-11-16

### Changed

- SKILL.md rewritten as a procedure (522 to 111 lines): routing table,
  ten numbered steps with commands, a signal | action failure table,
  verification commands and a short checklist. Study measurements and the dated
  catalogue cases moved to references/skill-utility-evidence.md ("Diagnosed in
  this catalogue"). The skill now follows the rule it teaches in 2.5.0.
- Description cut from about 900 to 236 characters. Confusability on five
  task-shaped queries: 4/5 top-1, against 3/5 for the old description; the
  remaining miss ("meeting notes") loses to session-memory under both.
- New step: commit each skill's version bump separately, because the release
  bot writes the commit subject into every bumped skill's CHANGELOG.

## [2.5.0] - 2026-11-16

### Other

- creating-skill: diagnosed failures as signal-action rows, stories to CHANGELOG (2.5.0)

## [2.5.0] - 2026-11-16

### Changed

- Diagnosed failures now go in the body as signal → action rows only; the date,
  incident and discovery story go in the CHANGELOG. "Provide Context" is limited
  to one clause, and only where it changes what the reader does. Prompted by
  Oskar on building-property-tests 0.1.0, which followed the old guidance and
  shipped a SKILL.md full of dated case histories.

## [2.4.0] - 2026-11-13

### Other

- creating-skill: no selling in skill bodies; hunting-failing-inputs: trim references

## [2.4.0] - 2026-11-13

### Added
- "Write for a reader who already chose the skill": SKILL.md and the
  references carry no motivation, provenance or results. Those go in the
  CHANGELOG. Diagnosed on `hunting-failing-inputs`.
- Description length: aim for about 250 characters with three phrasings. The
  1024 limit is not a target.

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