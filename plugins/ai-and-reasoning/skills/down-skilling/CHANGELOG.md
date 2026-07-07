# down-skilling - Changelog

All notable changes to the `down-skilling` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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