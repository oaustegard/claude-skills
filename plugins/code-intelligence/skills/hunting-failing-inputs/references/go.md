# Go

Reference for step 3 (model) and step 5 (strict harness) of the procedure.
Source: Google Developers blog, 2026-11-12, "Catch Go bugs that fuzzing
misses with Gemini and a constraint solver".

## Listing traps: use the compiler

`list_traps.py` lists every index and slice. Go's prove pass has already removed
the ones it can show safe, and `bce_targets.py` lists only the ones that survive:

```bash
python3 scripts/bce_targets.py <module-dir> [./pkg/...] [--func Name]
```

It wraps `go build -gcflags=-d=ssa/check_bce/debug=1`. Zero checks in a
function means the compiler proved every access in range, which is a real
proof for the current code. On the example, `list_traps` finds 8 traps and the
compiler keeps 4. An inlined callee's check is reported at the call-site line.
`--goarch riscv64` (the post's setup) listed the same checks as amd64 on
go1.24.7.

## What each trap does on failure

| operation | out of range | model with |
|---|---|---|
| `s[i]` | panic | `index_oob(i, n)` |
| `s[lo:hi]` | panic if `hi > cap(s)`, **not** `len(s)`. Between `len` and `cap` it silently reads past the input | `go_slice_oob(lo, hi, cap)` |
| `uint8` / `int8` arithmetic | silent wrap, before any `int(...)` conversion | `byte_at`, then `widen(x, signed=...)` at the conversion |

## Strict harness

Add `d = d[:len(d):len(d)]` as the first line of every
`f.Fuzz(func(t *testing.T, d []byte) {...})` body. Fuzzer inputs carry spare
capacity, so without that line an overrun up to `cap` passes silently. In
reproducers, give the function `append([]byte(nil), b...)[:len(b):len(b)]`.

## Worked example: `examples/go/`

`parse.go` has the post's two bug classes: a `uint8` length sum that wraps
before the guard (`ParseTwoChunkFrame`), and a trailing backslash that moves
the index past the end (`ExtractQuotedToken`). Each `TestZ3_*` in
`z3repro_test.go` panics at the line its trap names (14, 16, 33).

Unseeded `go test -fuzz`, 30 s each: the plain harness found neither bug. With
`d = d[:len(d):len(d)]`, it found both in under a second.
