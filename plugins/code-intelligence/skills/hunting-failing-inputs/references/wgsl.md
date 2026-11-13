# WGSL (WebGPU compute)

Nothing in WGSL faults:

| operation | out of range | predicate |
|---|---|---|
| `a[i]` read, runtime-sized array | returns a value from somewhere in the buffer, or zero | `UGE(i, n)` |
| `a[i] = v` | the write is dropped, or lands elsewhere in the buffer | `UGE(i, n)` |
| constant index into `array<T, N>` | compile error | — |
| `x / 0u` | returns `x` | `div_zero(y)` |
| `x % 0u` | returns `0` | `div_zero(y)` |
| `x << k` | `k` is taken mod 32 | `k >= 32` |
| `u32` / `i32` arithmetic | wraps | `word(name, 32)` |

Compare `u32` values with `ULT`, `UGE` and `UGT`, because z3py's `<` and `>=`
are signed.

## Strict harness

```bash
python3 scripts/wgsl_guard.py kernel.wgsl kernel.guarded.wgsl   # prints the site table
```

Every index into a module-scope array, read or write, becomes
`a[_bc(u32(i), <len>, site)]`. An out-of-range index increments `_oob[0]` and
records the highest site + 1 in `_oob[1]`. The pass adds one binding: group 0,
the next free binding number (or `--group/--binding`), of type
`var<storage, read_write> _oob: array<atomic<u32>, 2>`. Bind an 8-byte zeroed
buffer there and read it back after the dispatch.

Limits: compute shaders only; module-scope arrays only; no checks on division
or shifts. Use it in tests only.

Run kernels with `compiling-wgsl`'s `scripts/harness/gpu.mjs` (headless
Chromium WebGPU on SwiftShader). `examples/wgsl/run.py` shows the job format.

## Example: `examples/wgsl/`

`gather.wgsl` checks `offset + count*stride <= arrayLength(&src)` in `u32`,
and the product wraps. `model.py` should report `src[...]` `sat` and `dst[i]`
`unsat`. `run.py` runs the plain and the guarded kernel: the plain kernel's
output shows no sign of the bug, while the guarded kernel's `_oob[0]` is
non-zero.
