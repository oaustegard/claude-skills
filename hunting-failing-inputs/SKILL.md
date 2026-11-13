---
name: hunting-failing-inputs
description: Finds inputs that make a parser, decoder or WGSL compute shader index out of bounds or overflow, using Z3. Use for "can this crash", "find an input that breaks this", or when fuzzing found nothing on code that reads untrusted bytes.
metadata:
  version: 0.3.0
---

# Hunting failing inputs

A **trap** is an operation with a precondition the input can break: an index
in range, a slice end within the length, a non-zero divisor, a sum that must
not wrap.

## Not for

| Situation | Use instead |
|---|---|
| Races, deadlocks, async ordering | race detector or stress test |
| Whole programs, I/O, network, UI | fuzzing plus sanitizers; extract the pure core first |
| Wrong results no precondition expresses | property tests against a reference, or `reasoning-semiformally` |
| Whether a test can go red | `gating` |
| Validating or minifying WGSL | `compiling-wgsl` |

Stop and report a trap as **unmodelled** (never as safe) when its model needs
more than about 15 unrolled loop iterations, needs heap state that a single
input cannot build, or returns `unknown` twice.

## Setup

```bash
python3 -m pip install z3-solver tree-sitter-language-pack
SKILL=/mnt/skills/user/hunting-failing-inputs
python3 $SKILL/scripts/selftest.py   # optional: SKIP means a missing toolchain, not a pass
```

## Procedure

1. **List the traps.**
   `python3 $SKILL/scripts/list_traps.py FILE... [--func NAME]` prints
   `file:line:col  kind  on-failure  func  source`. `on-failure` is `raises`,
   `silent` or `UB` (C, which is silent without sanitizers). Model the `silent`
   and `UB` traps first. Strike any trap that an earlier guard already makes
   safe, and in JS strike object lookups. For Go, use `bce_targets.py`
   instead (see `references/go.md`).

2. **Read `references/<lang>.md`** for the target's language: `python`,
   `javascript`, `c`, `wgsl` or `go`. Each one has the failure semantics, the
   predicate to model each trap with, the strict harness, and a runnable
   example in `examples/<lang>/`.

3. **Model one pure function.** Include the guards its callers enforce as
   constraints. Without them, Z3 invents inputs the program can never produce.

4. **Write the model** from `scripts/z3traps.py`, copying the nearest
   `examples/<lang>/model*.py`:

   ```python
   import sys; sys.path.insert(0, f'{SKILL}/scripts')
   from z3traps import *
   n, base = harness(max_len=64)
   b0 = byte_at('b0')
   base += [n >= 2]                     # every early return the path got past
   solve_traps(base, {'f.py:10 b[k:k+2]': slice_truncates(k, k + 2, n)}, show=(n, b0))
   ```

   - Do arithmetic at the width the language uses, and `widen` exactly where
     the source converts. Python ints never wrap. C narrows on a store or a
     cast, JS `|0` truncates to 32 bits, and WGSL `u32` and Go `uint8` wrap.
   - Write each guard the way the source writes it, including its overflow.
     A guard written the way it was meant models the fixed code.
   - Use the precondition the runtime actually checks. Go checks slices
     against `cap`. Python wraps silently only for `-len <= i < 0`.
   - Use `in_order=True` when the traps are on one straight-line path, and
     leave it off when they are on different branches.
   - For loops, try concrete lengths `L = 1, 2, …` with symbolic bytes, and
     stop at the first `sat`.
   - z3py's `<` and `>=` on bit-vectors are signed. For unsigned values,
     widen first or use `ULT`/`UGE`.

5. **Replay each `sat` inside the strict harness.** `literal(bytes, lang)`
   renders the input for a test. Use the harness for the language:

   | language | strict harness |
   |---|---|
   | Python | `parse(strict(data))`, `scripts/strict.py` |
   | JS / TS | `decode(strict(u8))`, `scripts/strict.mjs` |
   | C | `-fsanitize=address,undefined -fno-sanitize-recover=all`, input in an exact-size `malloc` |
   | WGSL | `scripts/wgsl_guard.py` counts bad indexes in an extra `_oob` buffer |
   | Go | `d = d[:len(d):len(d)]` |

   Then read the result:

   | Z3 | replay | meaning |
   |---|---|---|
   | `sat` | fails at the trap's line | A bug. Report it with the reproducer. |
   | `sat` | fails at an earlier line | Re-solve with `in_order=True`. |
   | `sat` | doesn't fail, or fails differently | The model is wrong. Fix it, and never report this as a bug. |
   | `unsat` | — | "None within len ≤ N", not "safe". |
   | `unknown` | — | Simplify the model. Never count it as `unsat`. |

6. **Fix, and keep the harness.** Patch the code, update the model and expect
   `unsat`, and keep the reproducer as a regression test. Add the strict
   harness to the project's existing fuzz targets and property tests.

## Verification

Every trap you didn't strike ends as one of:

- a reproducer that fails at that trap inside the strict harness
- `unsat` with a stated bound, plus a negative control that went `sat`
- unmodelled, with the reason

For the negative control, remove one guard or widen one field and expect
`sat`. If the model stays `unsat`, it is over-constrained and its `unsat`
means nothing.

## Failure modes

- **A `sat` input doesn't fail as predicted.** The model's precondition is
  wrong. On 2026-11-13, a Python model treated every negative index as a
  silent wrap, and its input `b'\x00\xc0'` raised `IndexError` instead.
- **A later trap's `sat` input fails at an earlier line.** Use
  `in_order=True`. On 2026-11-13, the Go line-16 input panicked at line 14.
- **Every trap is `unsat`, including the buggy ones.** A guard was modelled
  with wide arithmetic where the source uses narrow. Run the negative control.
- **The strict harness passes, but Z3 says `sat`.** The wrapper covers only
  the object you wrapped. Buffers the function builds itself are unwrapped.
- **Random testing finds nothing, even when strict.** Check the random source.
  On 2026-11-13, a JS LCG that lost precision past 2^53 never hit the bug.
- **clang fails to link ASan or libFuzzer.** `libclang-rt-<N>-dev` is
  missing. Install it, or use gcc.
