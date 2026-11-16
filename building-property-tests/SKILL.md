---
name: building-property-tests
description: Finds correctness bugs by checking code against a simple reference model over generated inputs and operation sequences, then shrinks each failure to a regression test and a fix. Use for "property test this", "model-based testing", "find bugs in this data structure", or a Hypothesis state machine.
metadata:
  version: 0.1.1
---

# Building property tests

## Not for

| Situation | Use |
|---|---|
| Input that crashes, indexes out of bounds or overflows | `hunting-failing-inputs` |
| Whether one existing check can go red | `gating` |
| Tests that copy a registry; declaring invariants | `declaring-invariants` |
| Performance claims | benchmarking |
| Code with no simpler description of correct behaviour than itself | example tests, or `reasoning-semiformally` |
| Races, async ordering | stress test or race detector |

Stop and switch to path-agreement properties only when the model grows as complex as the code. Stop and rewrite the contract (step 1) after three rounds where every failure was a harness bug.

## Setup

```bash
uv pip install --system --break-system-packages hypothesis pytest
uv pip install --system --break-system-packages -e /path/to/target
cd /tmp && python3 -c "import target; print(target.__file__)"   # None = namespace package; reinstall
git -C /path/to/target rev-parse HEAD                             # record the commit
```

Rust: `proptest` + `proptest-state-machine`. JS/TS: `fast-check` with `fc.commands`/`fc.modelRun`.

## Procedure

1. **Write one contract per target**, citing its source (`README.md:23`, `core.py:1261`). Pick targets where the code is complex and a correct model is simple; `references/targets.md` lists property kinds.

2. **Write the model** with plain loops, importing nothing from the target but the subject. List in the harness docstring anything the model shares with production (tables, matrices, tokenizers) as a blind spot.

3. **Write generators** from `assets/stateful_template.py`:
   - small pools (3–4 keys, few values), unequal overwrite values;
   - edge values as their own strategy (empty, n<k, k=n, duplicates, ties, unaligned sizes);
   - the sizes and modes the existing suite does not use — grep its tests first;
   - domains drawn from the registry, never a copied list;
   - `event("<class>")` on every interaction a property needs;
   - rare conjunctions built inside one rule.

4. **Get it green on code you believe correct, then check coverage:**
   ```bash
   python3 scripts/hypothesis_stats.py --min <class>=5 -- pytest -q test_props.py
   ```
   Exit 1 names classes below floor or never fired. Fix the generator; do not raise `max_examples`.

5. **Plant bugs.** Own code: `python3 /mnt/skills/user/gating/scripts/mutate.py --target src/x.py -- pytest -q test_props.py`. Installed library: a `MUTANT=<name>` monkeypatch branch (dropped invalidation, off-by-one, missing guard). Count a mutant as caught only on `AssertionError`. A survivor means generation, propagation or assertion is missing — fix and rerun.

6. **Triage each failure.** Reproduce it in a plain script outside the harness, then read both subject and model.

   | Class | Action |
   |---|---|
   | Violates the written contract | regression test, then fix |
   | No document pins the expectation | `xfail(strict=True)` test; ask the owner |
   | Documented limitation | note it |
   | Harness bug | fix the harness |

   Vary each suspected condition alone, probe sibling paths with the same invariant, then put the finding behind `SKIP_KNOWN` and keep searching.

7. **Write one deterministic regression per finding** (plain pytest, named after the contract). Run it on the unmodified commit and read the failure text: it must fail for the stated reason.

8. **Fix in a worktree and run all four:**
   ```bash
   git worktree add ../target-fix -b fixes
   PYTHONPATH=../target-fix pytest -q test_regressions.py          # pass
   PYTHONPATH=../target-fix SKIP_KNOWN=0 pytest -q test_props.py   # pass — catches fixes the regression accepts
   PYTHONPATH=../target-fix pytest -q ../target-fix/tests          # pass
   PYTHONPATH=/path/to/target pytest -q test_regressions.py        # still fails
   ```
   A fix that changes persisted output (stored codes, file layout, hashes) goes to the owner as a decision.

9. **Declare** the two or three properties the codebase depends on as `invariant:` tests with a `refuted:` line, following `declaring-invariants`, then run its `claims.py` and `totality_lint.py`.

10. **Place artifacts.** Target repo: one regression file mapping each test to its finding, the fixes, a changelog entry. Discovery harness, mutant results and event counts: an experiments repo, with a script that reruns the regressions on old and new commits.

For several independent areas, run steps 1–7 in parallel agents: `references/delegating.md`.

## Rules with exceptions

| Rule | Exception |
|---|---|
| The model imports nothing from the target | a constant table checked separately against a published anchor; list it as a blind spot |
| Compare paths with a tolerance | where docs say "byte-identical" or "same bits", use exact equality |
| Fix every confirmed finding | not when the fix changes persisted output |

## Failure modes

| Signal | Action |
|---|---|
| Green on the first full run | run steps 4–5 before believing it |
| A mutant "caught" by an exception from the mutant itself | require `AssertionError`; guard the mutant |
| Fails on some runs, not others | build the conjunction in one rule, or sweep fixed seeds; record the detection rate |
| Fails only at large float magnitudes | if two production paths agree, it is float32 rounding against your float64 model; scale the tolerance |
| Shrunk case doesn't reproduce | it needed an env switch (`SKIP_KNOWN=0`, `MUTANT`); record the env with every case |
| `FailedHealthCheck` filter_too_much | derive the value with `st.data()`/`flatmap` instead of filtering |
| Changes have no effect | stale editable install; print `target.__file__` in the session |

## Verification

```bash
pytest -q test_regressions.py                          # old commit: all fail
PYTHONPATH=<fixed> pytest -q test_regressions.py       # fix: all pass
PYTHONPATH=<fixed> SKIP_KNOWN=0 pytest -q test_props.py
python3 scripts/hypothesis_stats.py --min <class>=<floor> -- pytest -q test_props.py
MUTANT=<each> pytest -q test_props.py                  # each fails by AssertionError
```

Bad success: a regression that passes on the old commit; a fix that silently changes persisted output; a green suite whose relied-on events never fired.

## Credit

Adapted from Inanna Malick's `proptest-praxis` (github.com/inanna-malick/agent-skills, MIT, Copyright (c) 2026 Inanna Malick) and her post "Property Testing with Agent Swarms" (recursion.wtf).
