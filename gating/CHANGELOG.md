# gating - Changelog

All notable changes to the `gating` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
