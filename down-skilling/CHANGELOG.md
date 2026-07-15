# down-skilling - Changelog

All notable changes to the `down-skilling` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.3.0] - 2026-07-15

### Other

- Add agent-routing skill; update down-skilling with 2026-07-15 Haiku 4.5 calibration (#728)

## [1.3.0] - 2026-07-15

### Added

- **"Before Distilling: Check Whether the Task Needs It"** triage section.
  A 2026-07-15 empirical calibration (300 Haiku 4.5 calls; evidence in the
  `agent-routing` skill's `references/calibration-2026-07-15.md`) measured
  Haiku 4.5 at 240/240 on mechanically checkable work — nested arithmetic,
  30-hop chains, 25-op state tracking, trap math, 5-constraint generation —
  at low effort, beating Sonnet-low (17/20) on the same battery. For
  checkable outputs, a minimal prompt + deterministic verifier +
  escalate-on-fail now beats example-heavy distillation; distill fully only
  for judgment-shaped outputs.
- **Iteration warning**: blind self-improvement loops measured as
  identity-or-drift (0/96 changes on correct answers; regression-then-freeze
  on the one output that did change). Loop only with an out-of-band scorer,
  keep argmax, stop on first regression.

### Changed

- **Economics** section repriced to current models: Haiku 4.5 $1/$5,
  Opus 4.8 $5/$25 per MTok (5× both sides; was stated as ~6× on stale
  $0.80/$4.00 Haiku pricing).
- **gaps/counting-enumeration.md**: Haiku 4.5 measured 13/13 on exact
  word-count generation at N=10–14 under stacked constraints (Sonnet-low
  missed twice); decisive factor is defining the unit of counting in the
  prompt. Mitigations rescoped to large N and count-inside-long-output.
- **gaps/multi-hop-reasoning.md**: split hop types — explicit chains
  (lookups, state updates) measured 100% to 30 hops; the 2-3-hop caution
  now scoped to latent inference chains, which remain unmeasured.

## [1.2.0] - 2026-05-26

### Added

- add mapping-features skill for behavioral web app documentation (#432)
- restructure boot output for progressive disclosure

### Other

- down-skilling: add example-calibration rules (v1.2.0) (#674)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)

## [1.2.0] - 2026-05-26

### Added

- **Source-anchoring** requirement in Example Quality Criteria. Every
  concrete fact in an example output must trace to that example's
  input; invented facts cause Haiku to copy the invention pattern at
  runtime.
- **Length-calibration** requirement in Example Quality Criteria.
  Example output lengths must sit inside the stated output range —
  rules don't override the example central tendency.
- **"When the input could be abstract: model the silence"** subsection
  with a worked example showing the input → output pattern that lets
  Haiku acknowledge what the source omits rather than filling the gap.
- **Tagged BAD/GOOD pair** is now the default negative-example
  pattern for confabulation-prone tasks (rewriting, summarization,
  NL→command). Updated the distribution-table row to reflect this.
- **Activation step 5: audit your example set** — source-anchoring +
  length-calibration check before delivering the prompt. Existing
  Deliver step renumbered to 6.

### Why

Validated by experiments at
[oaustegard/claude-workspace/experiments/haiku-assessment/](https://github.com/oaustegard/claude-workspace/tree/main/experiments/haiku-assessment).
The un-calibrated voice-rewrite prompt produced architectural
hallucination in 19/20 Haiku runs; the calibrated rerun produced 0/5.

## [1.1.0] - 2026-03-02

### Added

- lean harder into n-shot examples as primary steering mechanism

## [1.0.0] - 2026-02-14

### Other

- Update SKILL.md metadata
- Add down-skilling skill