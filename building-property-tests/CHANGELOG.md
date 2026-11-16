# building-property-tests - Changelog

All notable changes to the `building-property-tests` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.1] - 2026-11-16

### Changed

- SKILL.md and both references cut to instructions: the dated case histories,
  framing and per-rule backstory are removed (they remain in 0.1.0's
  provenance above and in experiments/remex-proptest). SKILL.md 220 to 119
  lines, references 149 to 73.

## [0.1.0] - 2026-11-16

Initial release. Adapts the method of Inanna Malick's `proptest-praxis` skill
([inanna-malick/agent-skills](https://github.com/inanna-malick/agent-skills),
MIT) and her post
[Property Testing with Agent Swarms](https://recursion.wtf/posts/agents-and-property-tests/)
from Rust `proptest` to Python Hypothesis. Its harness calibration now runs
through `gating` and its invariant declaration through `declaring-invariants`.

### Provenance

Two runs on 2026-11-16 shaped the procedure:

- `oaustegard/experiments/bm25-proptest`: one harness on the bm25 skill found
  a cache that ignored file contents and an empty-vocabulary crash. Shipped as
  bm25 0.2.2. The property suite rejected a wrong first fix that the regression
  test accepted (step 8).
- `oaustegard/experiments/remex-proptest`: four Sonnet agents, one per area,
  on remex 2.2.0. Their regressions failed in 68 cases covering 21 defects,
  among them silent code corruption between the two `.npz` writers at
  `d*bits % 8 != 0` and a segfault after pickling the default quantizer.
  Fixed in remex 2.2.1. The harnesses caught 72 of 73 planted bugs.

### Added

- `SKILL.md`: ten-step procedure, routing table against `hunting-failing-inputs`,
  `gating` and `declaring-invariants`, earned exceptions, failure modes with
  their diagnosis dates.
- `scripts/hypothesis_stats.py`: runs a Hypothesis suite with statistics on and
  fails when a relied-on `event()` class falls below a floor or never fires.
- `assets/stateful_template.py`: a runnable `RuleBasedStateMachine` with a toy
  cached store, a planted mutant, a rejected-operation property and event
  counters.
- `references/targets.md`: property kinds, generator rules, tolerance rules,
  and where bugs were found.
- `references/delegating.md`: running one agent per area, the brief, the
  constraints that came from diagnosed stops, and the orchestrator's half.