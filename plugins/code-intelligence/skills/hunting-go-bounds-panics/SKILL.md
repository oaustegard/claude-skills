---
name: hunting-go-bounds-panics
description: Finds concrete inputs that make a Go function panic with "index out of range" or "slice bounds out of range", or shows that none exist up to a bound. Lists the bounds checks the Go compiler could not eliminate, models the path to each one as Z3 constraints, solves for a crashing input and replays it as a go test reproducer. Also fixes fuzz harnesses that hide slice overruns behind spare capacity. Use for "can this Go parser panic", "find a crashing input for this decoder", "fuzzing found nothing but I don't trust it", "harden this Go byte parser", "check_bce", "Z3 for Go", uint8 or int8 length fields, off-by-one in a Go scanner, or reviewing Go code that slices untrusted bytes.
metadata:
  version: 0.1.0
---

# Hunting Go bounds panics

Every bounds check the Go compiler keeps is a place the program can panic. The
compiler's prove pass already removed the checks it could show safe; this skill
works on the rest. For each surviving check, write a Z3 model of the path to it,
let Z3 find an input that reaches it out of range, and confirm the input
against the real function with `go test`.

Source: Google Developers blog, 2026-11-12, "Catch Go bugs that fuzzing misses
with Gemini and a constraint solver". The post used Gemini to write the models;
here you write them. Reproduced on 2026-11-13 with go1.24.7: Z3 found both
planted bugs in milliseconds, unseeded fuzzing missed both in 30 s, and the
one-line harness fix in step 6 made the fuzzer find both in under a second.
[references/worked-example.md](references/worked-example.md) has every file and
output from that run.

## When to use it, and when not

Use it on pure Go functions that index or slice their input: parsers, decoders,
framing and length-prefix readers, tokenizers, varint and escape handling, slice
utilities that take offsets or line numbers.

| Situation | Use instead |
|---|---|
| Data races, deadlocks, goroutine leaks | `go test -race`, `testing/synctest`, goroutine leak profiles |
| A whole CLI or server, file I/O, flags, network | fuzzing plus `-race`; extract the pure core first, then come back |
| Logic bugs that return a wrong answer without panicking | `reasoning-semiformally` |
| Whether a test or gate can actually go red | `gating` |
| A code-review finding to confirm or refute | `verifying-review-findings` |
| Rust, C, or another language | the method carries over, but `bce_targets.py` and `z3go.py` are Go-specific |
| `unsafe`, cgo, or reflection | these paths are not bounds-checked, so this skill cannot see them |

Abandon the run when a model needs more than about 15 symbolic loop iterations,
or heap state that a fixed input cannot set up, or when Z3 returns `unknown`
twice after you simplify. Report the traps you could not model as unmodelled.
Do not report them as safe.

## Setup

```bash
pip install z3-solver          # brings the z3 Python module and a z3 binary
go version                     # any recent toolchain; checked on go1.24.7
SKILL=/mnt/skills/user/hunting-go-bounds-panics   # or wherever this skill lives
```

`python3 -c "import z3"` failing after the install means pip installed into a
different interpreter than the one you run. Use `python3 -m pip install z3-solver`.

## Procedure

### 1. List the surviving checks

```bash
python3 $SKILL/scripts/bce_targets.py <module-dir> [./pkg/...] [--func Name]
```

Each line is `file:line:col  kind  func  source`, where `kind` is `index`
(`s[i]`) or `slice` (`s[a:b]`). The script wraps
`go build -gcflags=-d=ssa/check_bce/debug=1`.

- **Zero checks in a function**: the compiler proved every access in range.
  That is a real proof for the current code, so you are done with that
  function.
- **Exit 2**: the package did not compile. The output shows the compiler's
  errors.
- `--goarch riscv64` reproduces the post's setup. On go1.24.7 it listed the
  same checks as amd64, so leave it off unless the two disagree.

### 2. Cut the target down to a pure function

Model one function at a time, and include the guards its callers enforce. A
helper that relies on its caller to check `len(b) >= 4` gets that check as a
constraint in the model. Without it, Z3 will invent inputs that the program
can never produce. If the function reads files, flags or sockets, pull the
byte-handling core out into its own function first.

### 3. Write the model

Start each model from `$SKILL/scripts/z3go.py`:

```python
import sys; sys.path.insert(0, f'{SKILL}/scripts')
from z3go import *
n, base = harness(max_len=64)          # len(b) == cap(b), 0..64
b0 = byte_at('b0')                     # one symbolic byte per field you read
base += [n >= 2]                       # every early return the path passed
...
solve_traps(base, {'f.go:14 b[2:2+h]': slice_oob(lo, hi, n)}, show=(n, b0))
```

Rules that decide whether the model means anything:

1. **Model the width Go uses.** Arithmetic on `uint8` wraps at 256 and on
   `int8` at ±128, before any conversion to `int`. Use `BitVec(name, 8)` for
   bytes, and do the arithmetic at that width. Convert with
   `to_int(x, signed=...)` at the exact point the source does. Most bugs this
   skill finds are a narrow add feeding a wide comparison.
2. **Slices check against `cap`, not `len`.** `slice_oob` encodes
   `0 <= lo <= hi <= cap`, and the harness makes `cap == len`. `index_oob`
   encodes `0 <= i < len`.
3. **Add every guard the path passed** as a constraint, written the way the
   source writes it, including its overflow behaviour. If you model the guard
   as you think it was meant, you model the fixed code and miss the bug.
4. **One trap per query.** `solve_traps` gives each trap its own solver. Pass
   `in_order=True` when the traps are on one straight-line path, so that a
   later trap is only reached after the earlier ones pass. Leave it off when
   they are on different branches.
5. **Loops get a bounded unroll.** Make the input a list of symbolic bytes of
   concrete length `L`, and step the index with `If` for each iteration. Try
   `L` from 1 upward and stop at the first `sat`. The quoted-token model in the
   worked example shows the pattern.
6. **Read the assembly only when a conversion is ambiguous.** For example, you
   may need to know whether a value is truncated before or after a shift.
   `go build -gcflags=-S` prints it. The post fed RISC-V disassembly to its
   model writer. For the planted bugs, the Go source and the declared types
   were enough.

### 4. Turn each `sat` into a reproducer

Write one test per trap. Don't recover the panic, so the trace names the line:

```go
func fresh(b []byte) []byte { return append([]byte(nil), b...)[:len(b):len(b)] }

func TestZ3_f14(t *testing.T) {
	b := make([]byte, 64)
	b[0], b[1] = 126, 192          // from the model
	ParseTwoChunkFrame(fresh(b))
}
```

`go_literal(concrete_bytes(model, vars))` prints the bytes as a Go literal.

### 5. Read the results

| Z3 | `go test` | Meaning |
|---|---|---|
| `sat` | panics at the trap's `file:line` | A bug, with a reproducer. Report it. |
| `sat` | panics at a different line | An earlier check fires first. Re-solve with `in_order=True`, or report it under the line that actually panicked. |
| `sat` | no panic | The model is wrong. Usually a missed guard, a wrong width, or `len` used where Go checks `cap`. Fix the model, then re-solve. Never report this as a bug. |
| `unsat` | — | Safe only for this model and its bounds. Report it as "no panic within len ≤ N", never as "proven safe". |
| `unknown` | — | Simplify the model or tighten the bounds. Never count it as `unsat`. |

### 6. Fix, then re-check

1. Patch the function.
2. Update the model to match the patch, re-solve, and expect `unsat`.
3. Re-run the reproducer and expect no panic. Keep it as a regression test.
4. Add `d = d[:len(d):len(d)]` as the first line of every
   `f.Fuzz(func(t *testing.T, d []byte) {...})` body in the package. Fuzzer
   inputs carry spare capacity, so an overrun up to `cap` passes silently.
   Without this line, the fuzzer can generate the crashing input and still
   never see a panic.

## Verification

The run succeeded when every surviving check from step 1 ended in one of three
states:

- a reproducer that panics at that check's `file:line`
- `unsat` under a stated bound, with a negative control (below) that went `sat`
- listed as unmodelled, with the reason

**Negative control.** Before you trust an `unsat`, drop one guard from the
model, or widen a field. The query should go `sat`. If it stays `unsat`, the
model is over-constrained and cannot fail, so its `unsat` means nothing.

A bad success looks like a page of `unsat` results where no model was ever
seen to go `sat`, or a list of bugs where no reproducer was run.

## Failure modes

- **`sat` on a later trap, but the reproducer panics on an earlier line.** The
  query did not require the earlier checks to pass. Use `in_order=True` for
  straight-line traps. *Diagnosed 2026-11-13* while building this skill: trap
  16's first model was `len=52, hdrLen=249`, which panics at line 14.
- **Every trap is `unsat`, including the obviously buggy ones.** You probably
  wrote a guard with `int` arithmetic where the source uses `uint8`, which
  models the fixed code. Run the negative control.
- **`sat` with no panic.** The model checks against `len` where Go checks
  `cap`, or it skipped a guard. The reproducer must use `fresh(...)`. A plain
  `[]byte{...}` literal has `cap == len` too, but a sub-slice of a larger
  buffer does not.
- **A check is reported on a line that only holds a function call.** The
  callee was inlined, and its check is reported at the call site.
  `at(b, k)` on line 6 shows up as `inl.go:6 index`. Model the callee's
  index expression, using the caller's arguments.
- **`ModuleNotFoundError: z3`.** pip installed into another interpreter. Use
  `python3 -m pip install z3-solver`.

## Files

- `scripts/bce_targets.py`: lists the surviving bounds checks, each with its
  function and source line.
- `scripts/z3go.py`: Go index and slice semantics, the harness, a per-trap
  solver, and conversion of a model to bytes.
- `references/worked-example.md`: two planted bugs, both models, the
  reproducers, and the fuzz comparison, all from a real run.
