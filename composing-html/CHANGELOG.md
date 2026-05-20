# composing-html - Changelog

All notable changes to the `composing-html` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.0] - 2026-05-20

### Other

- composing-html: --set escape hatch for body_html (fix multi-line JSON failure mode) (#657)

## [0.3.0] - 2026-05-19

### Added

- `build.py build` now accepts `--set KEY=VALUE` and `--set KEY=@FILE` to
  assign or override spec fields from the command line. `@FILE` loads the
  file contents verbatim into the field, sidestepping JSON-string escaping
  for multi-line HTML / CSS / JS bodies. `--spec` is now optional when
  `--set` supplies every required field. `--set` overrides matching fields
  from `--spec`.
- Tests cover the new `--set` paths (inline values, file loads, override
  semantics, bad syntax, missing files) and end-to-end CLI invocation.

### Changed

- SKILL.md reframes the freeform workflow around `--set body_html=@body.html`
  as the recommended path for anything with a substantial body — the prior
  "write spec.json" instruction was prone to producing invalid JSON when
  models inlined multi-line HTML via heredoc. The spec-file path is now
  positioned as best-fit for templates with typed slots, where JSON earns
  its keep.

## [0.2.0] - 2026-05-09

### Other

- composing-html: lead with chrome + freeform; demote templates (#636) (#637)

## [0.2.0] - 2026-05-09

### Changed

- Reframe SKILL.md around chrome + `freeform` as the default workflow; demote templates to a "shortcuts for repeat structure" section. Surface the `references/palette.md` inventory (color tokens, type stacks, layout primitives, components, tabs/sortables/live-binds) inline in SKILL.md so it reads as the primary product, not an appendix (#636).

## [0.1.0] - 2026-05-09

### Other

- Add composing-html skill: progressive-disclosure HTML artifact composer (#634)