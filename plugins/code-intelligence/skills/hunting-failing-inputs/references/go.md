# Go

## Listing traps

Use the compiler rather than `list_traps.py`. It lists only the bounds checks
its prove pass could not remove:

```bash
python3 scripts/bce_targets.py <module-dir> [./pkg/...] [--func Name]
```

This wraps `go build -gcflags=-d=ssa/check_bce/debug=1`. A function with zero
checks has every access proven in range. An inlined callee's check is reported
at the call-site line.

| operation | out of range | predicate |
|---|---|---|
| `s[i]` | panic | `index_oob(i, n)` |
| `s[lo:hi]` | panic if `hi > cap`; between `len` and `cap` it silently reads past the input | `go_slice_oob(lo, hi, cap)` |
| `uint8` / `int8` arithmetic | silent wrap before `int(...)` | `byte_at`, then `widen(x, signed=...)` at the conversion |

## Strict harness

Make `d = d[:len(d):len(d)]` the first line of every fuzz body. In
reproducers, pass `append([]byte(nil), b...)[:len(b):len(b)]`.

## Example: `examples/go/`

`parse.go` contains a `uint8` length sum that wraps before the guard, and a
trailing-backslash index past the end. Each `TestZ3_*` in `z3repro_test.go`
should panic at the line it names (14, 16, 33).
