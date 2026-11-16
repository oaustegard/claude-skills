---
name: building-property-tests
description: Finds correctness bugs by checking code against a simple reference model over generated inputs and operation sequences, then shrinks each failure to a regression test and a fix. Use for "property test this", "model-based testing", "find bugs in this data structure", or a Hypothesis state machine.
metadata:
  version: 0.1.0
---

# Building property tests

A **harness** generates inputs and operation sequences, runs them against the
code under test and against a **reference model**, and fails on any
disagreement. The model is the simplest correct implementation you can write:
a dict for a cache, a list and a linear scan for an index, full recomputation
for incremental state. A **finding** is a disagreement you have reproduced
outside the harness and traced to a written contract. A **regression** is the
deterministic unit test that pins one finding.

The procedure ties two sibling skills into the loop. `gating` proves the
harness can go red. `declaring-invariants` turns the properties that matter
into declared invariants a commit gate can hold.

## When NOT to use this skill

| Situation | Use |
|---|---|
| An input that crashes a parser or decoder, indexes out of bounds or overflows | `hunting-failing-inputs` |
| Whether one existing check or gate can go red; a calibration gate for a published number | `gating` |
| A test that copies a registry; which invariants a repo declares | `declaring-invariants` |
| First orientation in an unfamiliar repo | `exploring-codebases` |
| Performance or latency claims | benchmarking; there is no model for speed |
| Code whose only description of correct behaviour is the code itself | hand-written examples, or `reasoning-semiformally` |
| Races and async ordering | a stress test or race detector |

**Abandon the run** when any of these holds:
- The model has grown as complex as the implementation. You are reimplementing
  it and will share its mistakes. Fall back to path-agreement and metamorphic
  properties only.
- Three rounds in a row of failures were all harness bugs. The contract is not
  written down; go back to step 1.
- An event you rely on stays under 1% after two generator rewrites. Write
  targeted examples instead.

## Setup

```bash
uv pip install --system --break-system-packages hypothesis pytest
uv pip install --system --break-system-packages -e /path/to/target    # editable
cd /tmp && python3 -c "import target; print(target.__file__)"
git -C /path/to/target rev-parse HEAD     # record the commit every claim is about
```

A `__file__` of `None` means `import target` resolved to a namespace package,
usually the source directory sitting in the working directory, and not the
installed package. Every test then runs against nothing you meant. Diagnosed on
a container restart, 2026-11-16: reinstall and recheck before running anything.

Rust: `proptest` with `proptest-state-machine`. JS/TS: `fast-check`, using
`fc.commands` with `fc.modelRun`. The steps below hold in each language.

## Procedure

**1. Pick targets and write each contract down.** Rank by complex implementation
against simple oracle, then by what the maintainers worry about.
`references/targets.md` lists property kinds and where bugs were found. For each
target, write a one-line contract citing its source (`README.md:23`,
`core.py:1261`). A failure with no written contract cannot be classified, so it
cannot become a finding.

**2. Write the model.** Use plain loops and import nothing from the target
except the subject itself. Then list what the model *does* share with
production: codebook tables, a dense matrix, a tokenizer. Write that list into
the harness docstring as a blind spot. This is `gating`'s anchor obligation: a
model that reuses a production helper agrees with it on that helper's bugs.

**3. Write the generators.** Start from `assets/stateful_template.py`, a
runnable state machine with a toy subject, a planted mutant and event
counters. Use small pools, unequal overwrite values, and edge values as their
own strategy. Generate the sizes and modes the existing suite does **not**
use: grep its tests first. Draw enumerated domains from the registry, not
from a copy. Put `event("<class>")` on every interaction a property depends on.

**4. Run, then measure coverage.** A failure on the first run is normal. Get
the harness green on the code you believe correct, then:

```bash
python3 scripts/hypothesis_stats.py --min overwrite-after-read=5 --min 'k<N=True'=10 \
    -- pytest -q test_props.py
```

Exit 1 names each class below its floor, or "never fired". Fix the generator
before raising `max_examples`. More examples of the wrong distribution buy
nothing.

**5. Calibrate with planted bugs.** For code you can edit, use
`gating/scripts/mutate.py --target src/x.py -- pytest -q test_props.py`. For an
installed library you must not edit, add a `MUTANT=<name>` branch that
monkeypatches one plausible defect: a dropped cache invalidation, an
off-by-one, a missing guard. Every mutant must fail **by AssertionError**.
A mutant that fails by crashing proves nothing about the assertions (see
Failure modes). A survivor means a missing link: the generator never reaches
the state, the bad state never reaches an output, or no assertion reads that
output. Strengthen the weakest link and rerun.

**6. Triage every failure.** Reproduce it in a plain script outside the
harness. Read both the subject and the model. Classify it as one of:

| Class | Action |
|---|---|
| Confirmed: violates the written contract | Regression test, then fix |
| Ambiguous: no document pins the expectation | `xfail(strict=True)` test; ask the owner |
| Documented limitation | Note it; no test |
| Harness bug | Fix the harness |

Then **generalise**. Vary each suspected condition alone and in combination,
and probe sibling paths that keep the same invariant. In remex, a warm cache
skipping a guard on one search path prompted a check of the other paths. Put
each confirmed finding behind `SKIP_KNOWN` so the search continues past it.

**7. Extract one deterministic regression per finding.** Use plain pytest with
no generator, named after the contract. Run it against the unmodified commit
and confirm it fails **for the stated reason**: read the failure text, not
just the exit code.

**8. Fix, and run all four checks.**

```bash
git worktree add ../target-fix -b fixes                          # harness keeps the original
PYTHONPATH=../target-fix pytest -q test_regressions.py           # all pass
PYTHONPATH=../target-fix SKIP_KNOWN=0 pytest -q test_props.py    # property suite on the fix
PYTHONPATH=../target-fix pytest -q ../target-fix/tests           # target's own suite
PYTHONPATH=/path/to/target pytest -q test_regressions.py         # still fails on the old code
```

The property run with `SKIP_KNOWN=0` is the one that catches a wrong fix.
Diagnosed 2026-11-16 on the bm25 skill: the first empty-vocabulary fix returned
`[]`. The regression, which checked only "no traceback", passed it. The
property `len(hits) == min(k, N)` rejected it.

**9. Declare what matters.** For the two or three properties the codebase
depends on, add a test whose docstring opens `invariant:`, break the code once,
watch it go red by name, and record a `refuted:` line. Then run:

```bash
python3 /mnt/skills/user/declaring-invariants/scripts/claims.py .
python3 /mnt/skills/user/declaring-invariants/scripts/totality_lint.py .
```

The procedure lives in `declaring-invariants`; run it there rather than from
memory.

**10. Place the artifacts.** The target repo gets one regression file whose
module docstring maps each test to its finding, plus the fixes and a changelog
entry. The discovery harness, mutant results and event counts stay outside the
target, in an experiments repository. Add a script there that reruns the
regressions against the old and new commits and writes the numbers the
write-up cites.

For a target with several independent areas, run steps 1–7 in parallel agents,
one per area: `references/delegating.md`.

## Earned exceptions

| Rule | Banned when | Earned when |
|---|---|---|
| The model imports nothing from the target | the shared piece is the subject or a helper with branches of its own | the shared piece is a constant table checked separately against a published anchor; list it as a blind spot |
| Fix every confirmed finding | — | the fix changes persisted output (stored codes, file layout, hashes); put it to the owner as a decision. remex 2.2.1 left its unconverged 8-bit codebook for this reason |
| Exact equality between paths | the docs only promise "close" | the docs say "byte-identical" or "same bits"; a tolerance would hide the 1-ulp disagreement, as it would have for remex's IVF flat scan |
| Every failure gets a regression | it is a harness bug or a documented limitation | — |

## Failure modes

- **The suite passes on the first full run** → assume it can't fail yet. Run
  step 4 and step 5 before believing it. The bm25 cache bug fell in four
  steps, once the pool had four names.
- **A mutant is "caught" by an exception from the mutant itself** → the catch
  proves nothing. Record which error types each mutant raised, and require only
  `AssertionError`. Diagnosed 2026-11-16: a bm25 mutant crashed on `None`
  once known-bug skipping was off, and was counted as caught.
- **A property fails on some runs and not others** → it needs a rare
  conjunction. Build the conjunction in one rule, or raise the example count
  for that property alone. Write the measured detection rate next to it. A
  property that fails in about 6% of runs as written was replaced with a
  deterministic sweep over 400 seeds (remex encode, 2026-11-16).
- **A float property fails only at large magnitudes** → check whether two
  production paths agree with each other. If they do, the gap is float32
  cancellation against your float64 model, not a bug. Scale the tolerance
  with the magnitude.
- **The shrunk example doesn't reproduce with the default settings** → it
  depended on an environment switch such as `SKIP_KNOWN=0` or a mutant. Record
  the exact environment beside every shrunk case. Diagnosed in the bm25
  write-up's review.
- **Hypothesis reports `FailedHealthCheck` (filter_too_much)** → a filter is
  rejecting most draws. Derive the dependent value with `st.data()` or
  `flatmap` instead of filtering.
- **An `import` of the target works but tests behave as if nothing changed**
  → a stale editable install, or a namespace package. Print
  `target.__file__` inside the test session.

## Verification

```bash
pytest -q test_regressions.py                         # on the old commit: every test fails
PYTHONPATH=<fixed> pytest -q test_regressions.py      # on the fix: every test passes
PYTHONPATH=<fixed> SKIP_KNOWN=0 pytest -q test_props.py
python3 scripts/hypothesis_stats.py --min <each relied-on class>=<floor> -- pytest -q test_props.py
MUTANT=<each> pytest -q test_props.py                 # every one fails by AssertionError
```

A **bad success** looks like one of these:
- A regression test that passes on the old commit: it does not capture the bug.
- A fix that passes the regressions while changing persisted output that
  nobody was told about.
- A green property suite whose relied-on events never fired.
- A write-up whose numbers come from a run nobody can repeat.

## Credit

Adapted from Inanna Malick's `proptest-praxis` skill
(github.com/inanna-malick/agent-skills, MIT, Copyright (c) 2026 Inanna Malick)
and her post "Property Testing with Agent Swarms" (recursion.wtf).
