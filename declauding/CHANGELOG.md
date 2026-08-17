# declauding - Changelog

All notable changes to the `declauding` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.0] - 2026-08-16

### Added

- `scripts/declaude_review.py` — stage-2 structural pass. Extracts headers, opening and closing sentences, and isolated one-sentence paragraphs, then judges only those against the structural entries in `references/register.md`. Gemini or Anthropic key, `--emit-prompt` fallback, `--slots` for extraction only.
- `tests/sample-structure.md` and `tests/sample-structure.html` — regression fixtures built from headers that shipped past the linter.

### Fixed

- `declaude_lint.py` now flattens HTML before scanning. `HEADER_RE` matched markdown headings only, so every header rule was silent on an HTML draft — three thesis-shaped headers, a comma-clause header and a coy header shipped past a clean report. Masthead `.subtitle` / `.eyebrow` / `.post-meta` elements are scanned as headings.

## [0.2.1] - 2026-08-16

### Other

- declauding 0.2.1 — register entry 37, dressed metaphor (#761)

## [0.2.1] - 2026-08-16

### Added

- Register entry 37, dressed metaphor: a figure of speech standing in for a
  mechanism you could have named ("wearing the costume of", "dressed up as",
  visceral imagery on a mundane observation). Entry 6 covers the locational
  special case; this is the general one. The entry states that no regex reaches
  it, and both its specimens shipped past a clean lint report, one of them into
  a patch headed for another project.
- Lint rule for mid-paragraph `X is A, not B`. The existing rule anchors on
  end-of-line, so it caught the construction only as a closer.
- Three specimens for entry 37 in `tests/sample-tics.md`, which now reports 62
  candidates across 24 categories. Two of the three are invisible to the linter
  by design, which is the entry's point.

## [0.2.0] - 2026-08-16

### Other

- declauding v0.2.0 — absorb the encyclopedic and chatbot register from humanizer (#760)

## [0.2.0] - 2026-08-16

Absorbs what a comparison against [blader/humanizer](https://github.com/blader/humanizer)
v2.9.1 (MIT) showed this skill was missing. Humanizer packages the Wikipedia AI
Cleanup project's *Signs of AI writing*; its coverage of encyclopedic and chatbot
slop is broader than the two vocabulary entries this register had.

Measured before porting: a probe of 19 humanizer specimens produced 2 candidates
from `declaude_lint.py`, neither for the right reason. It now produces 33 across
13 categories.

### Added

- Register entries 24 to 36, in a second block that names itself as a different
  family from the staging mechanisms: copula avoidance, participle tail, forced
  triad, elegant variation, false range, inline-header list, typographic tells,
  chatbot residue, filler and hedge stacking, speculative gap-filling,
  diff-anchored documentation, subjectless fragment, predicate-position
  hyphenation. The block states that several of them are phrase lists rather than
  mechanisms and will leak.
- "Do not invent specifics" in `SKILL.md`, and a fourth failure mode in workflow
  step 5. De-vaguing a sentence is how a register pass fabricates, and the skill
  previously warned only against changing claims, not against supplying a name or
  number the source does not have.
- Voice-sample precedence. A sample of the author's writing outranks every rule
  here, including the em-dash density guard.
- Three invocation modes: pasted text, file, and embedded (another agent calling
  this as one step, which returns text and nothing else).
- "Leave these alone" section: the positive signals of human writing, and the
  things that are not tells on their own.
- Linter rules for the new lexical entries, plus Title Case heading detection and
  document-level curly-quote and emoji counts. Eleven new categories.
- 13 new specimens in `tests/sample-tics.md`, which now reports 58 candidates
  across 23 categories. `tests/sample-clean.md` stays at 0.

### Changed

- Content preservation now licenses structural rearrangement: every claim
  survives, but paragraphs may merge or split and depth need not be uniform.

### Fixed

- `--skip-quoted` blanked spans before lines, so a bold marker inside a table
  cell could mis-pair the italic regex across lines and leave that row's
  specimens visible. It also never blanked code, so a tell quoted in backticks
  reported as a hit. Fenced blocks and inline spans are blanked now, and the
  line pass runs first.
- The emoji count included U+2190 to U+21FF and U+2300 to U+23FF, so a plain
  arrow or a technical symbol in ordinary prose reported as decoration.
  Narrowed to the emoji-presentation blocks.

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