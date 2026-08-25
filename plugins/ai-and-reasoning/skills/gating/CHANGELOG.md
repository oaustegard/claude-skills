# gating - Changelog

All notable changes to the `gating` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.0] - 2026-08-25

### Other

- top skills: separate by omission, and correct the guidance that said otherwise (#777)

## [0.2.0] - 2026-08-03

### Other

- gating 0.2.0: lessons from the first substantial use of the skill (#752)

## [0.2.0] - 2026-08-02

Lessons from the first substantial use of the skill — auditing and rebuilding
the calibration gate in `oaustegard/experiments/remex-vs-higgs-ablation`
(8 checks -> 166, 91 mutants, four false reds in the rebuilt gate). Every item
below is something the skill led into or failed to warn about, not a
hypothetical.

### Added

- `bracket()` takes `lo_inclusive` / `hi_inclusive`. A strict edge at an
  *attainable* theoretical bound reports red on a perfect result: a randomized
  Hadamard maps a coordinate spike to exactly 1/sqrt(d), the information-
  theoretic floor, and a strict `lo` blocked a real run.
- `known_bad(..., covers=(...))` names the checks a case exercises, and
  `report()` prints the checks no known-bad reaches. "We have a known-bad" and
  "we know which checks fire" are different claims; an audited gate had one
  known-bad covering 1 of 8 checks, and the check its result rested on
  *accepted* the same bad case.
- SKILL.md: validate a known-bad at the configuration it will run in — one
  tuned at m=2/K=16 stopped being bad at m=8/K=65536.
- SKILL.md + `anchors.md`: a statistical margin is not a practical floor. A
  paired estimator's se shrinks as the arms converge, so a 3-sigma threshold
  admitted a +0.0001 dB effect where real ones were 0.35-1.41 dB. The
  magnitude that matters has to come from an anchor.
- SKILL.md: two anti-pattern rows (significant-but-not-meaningful; strict
  bracket at an attainable optimum) and an explicit statement that a gate
  checks *correctness* and cannot check *comparability* — performance claims
  have no anchor in this framework.
- `auditing.md`: disable on-disk caches before mutation testing, or every
  mutation of the producing code survives for the wrong reason; and pin
  permanent mutation fixtures by code snippet, because survivor line numbers
  go stale the moment anyone edits above them.

## [0.1.0] - 2026-08-02

### Added

- initial release: build and audit deterministic verification gates
- three obligations — anchor, known-bad, stated coverage limit
- `scripts/gate.py`: harness that reports INCONCLUSIVE (exit 2) rather than
  PASS when no known-bad or no coverage limit was registered
- `scripts/mutate.py`: stdlib token-level mutation pass over any gate command;
  refuses to run against an already-red gate, restores targets on interrupt
- `references/anchors.md`: six kinds of oracle strongest-first, what to do when
  nothing published exists, anchor hygiene
- `references/auditing.md`: six-pass "can this check fail?" sweep, with
  CONFIRMED / PLAUSIBLE / CANNOT FAIL / BLIND reporting resolution