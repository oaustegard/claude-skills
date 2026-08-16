# declauding - Changelog

All notable changes to the `declauding` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.1] - 2026-08-16

### Other

- declauding v0.1.1 — add README, --skip-quoted, and the fixes that missed #755 (#756)

## [0.1.1] - 2026-08-16

### Added

- `README.md`. Missing from 0.1.0: the commits carrying it landed on the branch after the merge and were lost when the branch was deleted.
- `--skip-quoted` on the linter. Blanks blockquotes, table rows, `*italic*` spans and `<q>` elements while preserving line numbers, so a document that quotes bad prose as specimens does not report its own examples. Handles italics that wrap across lines.

### Fixed

- The `earns/wants/demands` agency rule fired on ordinary second-person prose ("if you want the noise"). Added a lookbehind for personal pronouns.
- Density checks counted headings, table rows and list bullets as sentences, inflating fragment density on any structured document.
- The skill's own prose failed its own linter: two coy headers, four `X, not Y` closers, one abstraction-agency subject, and a negation-first closer sitting directly beneath the sentence explaining why negation-first closers are a tic.

## [0.1.0] - 2026-08-16

### Added

- Initial release. Two modes: clean rewrite (default) and annotated HTML diff.
- `references/register.md`: 23 entries grouped by mechanism, each with surface tell, why, fix, and a before-and-after from a real published draft. Grouping is by mechanism rather than phrase because phrase blocklists miss the next paraphrase.
- `references/annotating.md`: spec for the annotated diff.
- `assets/annotated.template.html`: self-contained output template. No build step, no CDN, opens from `file://`.
- `scripts/declaude_lint.py`: stdlib-only scan for lexical tells plus header shape, one-line-paragraph beats, fragment runs, em-dash density and sentence-length monotony. Exits 1 on candidates.
- `tests/sample-tics.md` (29 candidates, 12 categories) and `tests/sample-clean.md` (0). The clean corpus is human-written prose and holding it at zero is the linter's design constraint.
- Overcorrection guard and earned-exception table in `SKILL.md`.
- Workflow steps 1 and 6: read the whole piece first, and report contradictions separately rather than fixing them silently.

### Other

- declauding v0.1.0 — LLM prose tics in, human technical prose out (#755)