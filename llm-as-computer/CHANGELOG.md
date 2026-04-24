# llm-as-computer - Changelog

All notable changes to the `llm-as-computer` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.1.0] - 2026-04-24

### Added

- `specialize.py`: Percepta-style partial-evaluation pass. Bakes a compiled
  program into `2N` ReGLU step-function neurons + per-field coefficient
  tables; fetched `(op, arg)` at any cursor is reconstructed from
  `c0 + Σᵢ (cᵢ − cᵢ₋₁)·𝟙[cursor ≥ i]`, no program prefix required.
- `runner.execute(..., specialize=True)` / `runner.run(..., specialize=True)`:
  runs the specialized executor; traces match the universal interpreter
  step-for-step (verified across countdown, fibonacci, factorial,
  sum_1_to_n, power_of_2 and all 10 `ALL_TESTS` regression programs).
- `programs.make_countdown(n)`: canonical specialization demo target.
- `format_trace` now reports FFN neuron count and
  `universal → specialized` prompt-token savings when `specialize=True`.

### Notes

- `executor.mojo` intentionally untouched: its fetch path is already direct
  `List[Int]` indexing, so specialization offers no Mojo-runtime speedup.
  The demonstration is architectural (programs-as-weights) and
  prompt-size (#576).

## [1.0.1] - 2026-03-25

### Other

- llm-as-computer: raise step limits, add --max-steps and --quiet CLI flags (#465)

## [1.0.1] - 2026-03-25

### Changed

- executor.mojo: raise default max_steps from 50K to 5M
- executor.mojo: add `--max-steps N` CLI flag for runtime override
- executor.mojo: add `--quiet` flag to suppress per-step trace output
- runner.py: raise all default max_steps to 5M
- runner.py: pass `--max-steps` through to Mojo binary
- runner.py: scale subprocess timeout with step count

## [1.0.0] - 2026-03-25

### Other

- Add llm-as-computer skill: src/setup.sh
- Add llm-as-computer skill: src/executor.mojo
- Add llm-as-computer skill: src/runner.py
- Add llm-as-computer skill: src/programs.py
- Add llm-as-computer skill: src/isa_lite.py
- Add llm-as-computer skill: SKILL.md