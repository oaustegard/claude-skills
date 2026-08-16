# declauding - Changelog

All notable changes to the `declauding` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0] - 2026-08-16

### Added

- Initial release. Two modes: clean rewrite (default) and annotated HTML diff.
- `references/register.md`: 23 entries grouped by mechanism, each with surface tell, why, fix, and a before-and-after from a real published draft. Grouping is by mechanism rather than phrase because phrase blocklists miss the next paraphrase.
- `references/annotating.md`: spec for the annotated diff: markup for changed spans, edit notes, kept passages, flagged contradictions, and the tally table.
- `assets/annotated.template.html`: self-contained output template. No build step, no CDN, opens from `file://`.
- `scripts/declaude_lint.py`: stdlib-only scan for lexical tells plus header shape, one-line-paragraph beats, fragment runs, em-dash density and sentence-length monotony. Exits 1 on candidates.
- `tests/sample-tics.md` (29 candidates, 12 categories) and `tests/sample-clean.md` (0). The clean corpus is human-written prose and holding it at zero is the linter's design constraint; two header rules are tuned down to keep it there.
- Overcorrection guard and earned-exception table in `SKILL.md`. The failure mode of a de-tic pass is prose with no confidence, rhythm or opinions, so the guard is written in rather than left to judgment.
- Workflow steps 1 and 6: read the whole piece first, and report contradictions separately rather than fixing them silently. Sentences built for shape are disproportionately likely to be wrong. The source draft contradicted two of its own significance designations within two paragraphs.

### Provenance

Derived from a register pass on an external benchmark post, 2026-08-16: 34 passages, ~45 tic instances, ten shapes.
