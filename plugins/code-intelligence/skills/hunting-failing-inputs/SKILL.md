---
name: hunting-failing-inputs
description: Finds inputs that make a parser, decoder or WGSL compute shader index out of bounds or overflow, using Z3. Use for "can this crash", "find an input that breaks this", or when fuzzing found nothing on code that reads untrusted bytes.
metadata:
  version: 0.2.1
---

# Hunting failing inputs

A function that reads untrusted bytes fails where some operation's
precondition does not hold: an index that must be in range, a slice end that
must not pass the length, a divisor that must not be zero, a length sum that
must not wrap. Fuzzers only see the failures that make noise. In Python, JS,
WGSL and unsanitized C, most of these failures are silent. This skill lists
each such operation (a **trap**) and writes a Z3 model of the path that
reaches it. Z3 then finds an input that breaks the precondition, and the input
is replayed against the real code.

Adapted from Google's 2026-11-12 post "Catch Go bugs that fuzzing misses with
Gemini and a constraint solver", which applied it to Go bounds checks. On
2026-11-13 the method was reproduced in five languages. Z3 found every planted
bug. Plain fuzzing or random testing missed at least one bug in each of the
four languages where it was run. For WGSL, the odds of a random hit were
computed (about 2^-26 per input) rather than run. The numbers are in each
language's reference.

## When to use it, and when not

Use it on pure functions that index, slice, copy or divide by values derived
from their input: binary format parsers, decoders and decompressors, length-
prefixed framing, tokenizers, GPU kernels whose indexes come from parameters.

| Situation | Use instead |
|---|---|
| Data races, deadlocks, async ordering | the language's race detector or a stress test |
| Whole programs, I/O, network, UI | fuzzing plus sanitizers; extract the pure core first, then come back |
| Wrong results that no precondition can express | property tests against a reference implementation, or `reasoning-semiformally` |
| Whether a test or gate can actually go red | `gating` |
| A code-review finding to confirm or refute | `verifying-review-findings` |
| Validating or minifying a WGSL shader | `compiling-wgsl` (this skill borrows its GPU harness) |

Abandon the run when a model needs more than about 15 symbolic loop
iterations, or heap state that a single input cannot set up, or when Z3 returns
`unknown` twice after you simplify. Report those traps as unmodelled, never as
safe.

## Setup

```bash
python3 -m pip install z3-solver tree-sitter-language-pack
SKILL=/mnt/skills/user/hunting-failing-inputs     # or wherever this skill lives
python3 $SKILL/scripts/selftest.py                # reruns every worked example
```

The self-test prints PASS, FAIL or SKIP per check. A check whose toolchain is
missing (node, gcc, go, or playwright for WGSL) is skipped, never passed.

## Procedure

### 1. List the traps

```bash
python3 $SKILL/scripts/list_traps.py FILE... [--func NAME]
```

Each line is `file:line:col  kind  on-failure  func  source`. The `on-failure`
column says what happens at runtime when the precondition breaks:

- `raises`: the runtime signals it (`IndexError`, `RangeError`, a Go panic).
- `silent`: the program continues with a wrong value.
- `UB`: C undefined behaviour, which is silent unless sanitizers are on.

`silent` and `UB` traps are the ones a fuzzer cannot see, so model those first.
For Go, use `bce_targets.py` instead. It lists only the checks the compiler
could not prove safe (see `references/go.md`).

The lister is syntactic. It includes traps an earlier guard already makes
safe, and in JS it cannot tell array indexing from object lookup. Strike those
by reading the code, not by modelling them.

### 2. Load the language reference

Read the one for the language of the target. It has the failure semantics
table, the strict harness, and a worked example with a runnable model:
`references/python.md`, `javascript.md`, `c.md`, `wgsl.md`, `go.md`.

### 3. Cut the target down to a pure function

Model one function at a time, and include the guards its callers enforce. A
helper whose caller checks `len(b) >= 4` gets that check as a constraint.
Without it, Z3 invents inputs the program can never produce.

### 4. Write the model

Start from `scripts/z3traps.py` and copy the shape of the nearest example in
`examples/<lang>/model*.py`:

```python
import sys; sys.path.insert(0, f'{SKILL}/scripts')
from z3traps import *
n, base = harness(max_len=64)          # symbolic input length, bounded
b0 = byte_at('b0')                     # one symbolic byte per field read
base += [n >= 2]                       # every early return the path got past
...
solve_traps(base, {'f.py:10 b[k:k+2]': slice_truncates(k, k + 2, n)}, show=(n, b0))
```

These rules decide whether the model means anything:

1. **Model each value at the width the language uses.** Python ints never
   wrap. C narrows on store or cast, JS `|0` truncates to 32 bits, WGSL `u32`
   and Go `uint8` wrap. Do narrow arithmetic at its own width, and `widen`
   exactly where the source converts. A narrow add feeding a wide comparison
   is the most common bug this method finds.
2. **Use the precondition the runtime checks, not the one you expect.** For
   example, Go checks a slice against `cap`, Python's silent wrap only covers
   `-len <= i < 0`, and C checks nothing. The predicates in `z3traps.py`
   encode these. Each language reference says which predicate goes with which
   operation.
3. **Add every guard the path passed, written the way the source writes it,**
   including its overflow behaviour. If you write the guard the way it was
   meant, you are modelling the fixed code and the model cannot find the bug.
4. **Use one query per trap.** `solve_traps` does this. Pass
   `in_order=True` when the traps lie on one straight-line path, so a later
   trap requires the earlier ones to pass. Leave it off for traps on
   different branches.
5. **Unroll loops for a bounded length.** Make the input a list of symbolic
   bytes of concrete length `L`, step the state with `If`, and try `L` from 1
   upward, stopping at the first `sat`. `examples/python/model_lz.py` and
   `examples/go/model_quoted.py` show the pattern.
6. **z3py's `<`, `>=` and the other comparison operators on bit-vectors are
   signed.** For unsigned values, `widen` first or use `ULT`, `UGE` and `UGT`
   from `z3`.

### 5. Replay each `sat` against the real code

Write one test per trap, using the input the model printed (`literal(bytes,
lang)` renders it). Run it inside the language's **strict harness**, which
turns a silent trap into a loud one:

| language | strict harness |
|---|---|
| Python | `parse(strict(data))` from `scripts/strict.py` |
| JS / TS | `decode(strict(u8))` from `scripts/strict.mjs` |
| C | `-fsanitize=address,undefined -fno-sanitize-recover=all`, with the input in an exact-size `malloc` |
| WGSL | `scripts/wgsl_guard.py` rewrites every index to count out-of-range ones in an extra `_oob` buffer |
| Go | `d = d[:len(d):len(d)]`, so that `cap == len` |

Then read the result:

| Z3 | replay | meaning |
|---|---|---|
| `sat` | fails at the trap's line | A bug, with a reproducer. Report it. |
| `sat` | fails at an earlier line | An earlier trap fires first. Re-solve with `in_order=True`, or report the bug under the line that actually failed. |
| `sat` | does not fail, or fails differently than the model said | The model is wrong (a missed guard, a wrong width or a wrong predicate). Fix it and re-solve. Never report this as a bug. |
| `unsat` | — | No failure for this model and its bounds. Report it as "none within len ≤ N", never as "proven safe". |
| `unknown` | — | Simplify the model or tighten the bounds. Never count `unknown` as `unsat`. |

### 6. Fix, then keep the harness

1. Patch the function.
2. Update the model to match the patch, re-solve, and expect `unsat`.
3. Re-run the reproducer and expect it to pass. Keep it as a regression test.
4. Put the strict harness into the project's existing fuzz targets and
   property tests. It is cheap: in the worked examples, it took fuzzing from
   finding nothing to finding the bug in under a second (Go), after 1,581
   inputs (Python), and after 4,413 inputs (JS). For C, sanitizers did the
   same, cutting 77M fruitless runs to about 250.

## Verification

The run succeeded when every `silent`, `UB` and `raises` trap from step 1 that
you did not strike ended in one of three states:

- a reproducer that fails at that trap, inside the strict harness
- `unsat` under a stated bound, with a negative control (below) that went `sat`
- listed as unmodelled, with the reason

**Negative control.** Before you trust an `unsat`, remove one guard from the
model, or widen a field, and expect `sat`. If it stays `unsat`, the model is
over-constrained and cannot fail, so its `unsat` means nothing.

A bad success looks like a page of `unsat` results where no model was ever
seen to go `sat`, or a list of bugs where no reproducer was run.

## Failure modes

- **A `sat` input does not fail, or fails differently than predicted.** The
  model encodes the wrong precondition. *Diagnosed 2026-11-13*: a Python model
  treated every negative index as a silent wrap. Its input `b'\x00\xc0'`
  raised `IndexError` instead, because Python wraps only for `-len <= i < 0`.
  `negative_index(i, n)` now encodes that range.
- **A `sat` on a later trap whose reproducer fails at an earlier line.** The
  query did not require the earlier trap to pass. *Diagnosed 2026-11-13* on Go
  line 16: `len=52, hdrLen=249` panicked at line 14. Use `in_order=True`.
- **Every trap is `unsat`, including the obviously buggy ones.** The guard was
  written with wide arithmetic where the source uses narrow arithmetic, which
  models the fixed code. Run the negative control.
- **An unsigned value compares wrong.** z3py bit-vector `<` and `>=` are
  signed. A byte of 200 compares below 128 unless you widen it first.
- **The strict harness passes, but the model says `sat`.** The wrapper covers
  only the object you wrapped. A buffer the function builds itself (Python
  `out = []`, a JS `new Float32Array`) is unwrapped, so trust the reproducer
  that targets that buffer.
- **Random testing finds nothing, even with the strict harness.** Check the
  random source before blaming the harness. *Diagnosed 2026-11-13*: a JS LCG
  that multiplied past 2^53 produced inputs that never hit the bug. A
  `Math.imul`-based generator found it after 4,413 inputs.
- **Some checks are SKIP in `selftest.py`.** A toolchain is missing. clang
  without `libclang-rt-<N>-dev` cannot link ASan or libFuzzer, so use gcc or
  install the package. The WGSL GPU check needs node, playwright and the
  `compiling-wgsl` skill installed alongside this one.

## Files

- `scripts/list_traps.py`: lists traps for Python, JS/TS, C, WGSL and Go,
  using tree-sitter.
- `scripts/bce_targets.py`: lists Go's bounds checks that survive the
  compiler's prove pass.
- `scripts/z3traps.py`: trap predicates, the width and conversion helpers,
  per-trap solving, and literal rendering.
- `scripts/strict.py`, `scripts/strict.mjs`: strict wrappers for Python
  sequences and JS arrays and typed arrays.
- `scripts/wgsl_guard.py`: the WGSL instrumentation pass that records
  out-of-range indexes.
- `scripts/selftest.py`: reruns every example and checks its documented
  outcome.
- `references/<lang>.md`: per-language semantics, harness and worked example.
- `examples/<lang>/`: the planted-bug code, models and reproducers behind
  each reference.
