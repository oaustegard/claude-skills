# down-skilling - Changelog

All notable changes to the `down-skilling` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.6.0] - 2026-10-07

### Other

- down-skilling 1.6.0: anti-invention examples optional on Haiku 5.5

## [1.6.0] - 2026-10-07

### Changed

- The anti-invention ("model the silence") examples are optional on Haiku 5.5. A retest on the original rewrite task, 8 runs per version (`experiments/downskill-shots`, round 2), found 0/8 invented technical details for every version. That includes the example set that produced 19/20 on Haiku 4.5. The no-invention rule and the fact-listing step stay: without them, 3/8 rewrites invented facts.

## [1.5.0] - 2026-10-07

### Other

- down-skilling 1.5.0: start bare on Haiku 5.5

## [1.5.0] - 2026-10-07

### Added

- A "Start Bare" procedure for Haiku 5.5. Write the bare prompt and a 10–20 item test set, then add one rule for each unstated default and one example for each judgment boundary a run misses. Measured on three of the skill's own prompts (`experiments/downskill-shots`): rule-determined items scored 40/40 with or without examples. Items an example settles scored 22/24 as shipped, 20/24 bare, and 15/24 with the examples stripped but the rules kept.

### Changed

- Example count and sizing guidance (4–7 examples, examples as the largest section) is now labelled as the Haiku 4.5 method. The workflow step and the prompt architecture template name both models.

## [1.4.0] - 2026-10-07

### Other

- Retarget model-choice guidance to the 5.5 generation

## [1.4.0] - 2026-10-07

### Changed

- Retargeted to Haiku 5.5 ($0.10/$0.50, 40× under Opus 5.5 and 20× under Sonnet 5.5). The economics section no longer says retries erase the saving. It now points at silent errors as the cost examples prevent, and at the verifier plus informed retry that `agent-routing` measured on Haiku 5.5. The context note reflects Haiku 5.5's 1M window and its 100K-token price step. The 2026-07 calibration and the gap catalog stay labelled as Haiku 4.5 data.

## [1.3.1] - 2026-09-09

### Other

- prompt-audit: dated prompting patterns across the skill catalogue (#791)
- Add README.md to agent-routing and down-skilling (#729)

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