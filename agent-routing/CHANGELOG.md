# agent-routing - Changelog

All notable changes to the `agent-routing` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.4.0] - 2026-08-16

### Fixed

- repair broken frontmatter, mark obsolete skills, close registry gaps (#746)

### Other

- agent-routing 1.4.0: correct subagent-inheritance claim, add per-node kernel cost (#757)

## [1.4.0] - 2026-08-16

### Changed

- Context handoff: corrected "subagents inherit nothing" — measured on a CCotw Workflow node (run `wf_125b7073-75f`): nodes inherit the project layer (system prompt + CLAUDE.md) but not the conversation or in-session artifacts.

### Added

- Fixed per-node kernel cost: ~33k tokens/node measured for trivial tasks under a heavy CLAUDE.md; budget fan-outs as N × kernel and batch small checkable items into fewer agents.

## [1.3.0] - 2026-07-24

### Added

- Add/Update skill: agent-routing (#745)