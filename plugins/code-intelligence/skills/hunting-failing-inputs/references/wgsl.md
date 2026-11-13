# WGSL (WebGPU compute)

Reference for step 3 (model) and step 5 (strict harness) of the procedure.

## What each trap does on failure

Nothing in WGSL faults. Every row is silent.

| operation | out of range | model with |
|---|---|---|
| `a[i]` read, runtime-sized storage array | robust access: returns a value from somewhere in the buffer (SwiftShader returned the last element), or zero | `UGE(i, n)` |
| `a[i] = v` | write dropped, or lands somewhere in the buffer | `UGE(i, n)` |
| `a[i]`, fixed-size `array<T, N>`, constant index | compile error | — |
| `x / 0u`, `x % 0u` | integer `/` returns `x`; `%` returns `0` | `div_zero(y)` |
| `x << k` | `k` is masked to the low 5 bits | `k >= 32` |
| `u32` / `i32` arithmetic | wraps | `word(name, 32)` |

Use the unsigned comparisons from `z3` (`ULT`, `UGE`, `UGT`) for `u32`. The
z3py operators `<` and `>=` on bit-vectors are signed.

## Strict harness: `wgsl_guard.py`

```bash
python3 scripts/wgsl_guard.py kernel.wgsl kernel.guarded.wgsl   # prints the site table
```

Every index into a module-scope array, read or written, becomes
`a[_bc(u32(i), arrayLength(&a), site)]`. An index out of range increments
`_oob[0]` and records the highest `site + 1` in `_oob[1]`. The pass adds one
binding, `var<storage, read_write> _oob: array<atomic<u32>, 2>`, in group 0 at
the next free binding number (or `--group/--binding`). Bind an 8-byte zeroed
buffer there and read it back after the dispatch. A negative `i32` index
becomes a huge `u32` and is counted.

Limits: compute shaders only (vertex stages cannot write storage buffers),
module-scope arrays only (not function-local arrays), and nothing for
division or shifts. The rewrite changes timing and register pressure, so use
it to test, never in production.

To run a kernel, use the `compiling-wgsl` skill's
`scripts/harness/gpu.mjs`: headless Chromium WebGPU on SwiftShader, with
`kind: "compute"` jobs. `examples/wgsl/run.py` shows the job format.

## Worked example: `examples/wgsl/`

`gather.wgsl` reads `src[offset + i*stride]` after checking
`offset + count*stride <= arrayLength(&src)` in `u32`. The product wraps.
`model.py` finds `offset=2147483651, stride=2850296479, count=55`, where every
thread reads out of range. `dst[i]` is `unsat`.

On SwiftShader (`run.py`):

| kernel | result |
|---|---|
| plain | `dst[52:56] = (1063, 1063, 1063, 0)`: every read clamped to `src[63]`, no error |
| guarded | the same output and `_oob = [55, 2]`: 55 bad indexes, highest site 1 (`src[...]`) |

Random `u32` parameters hit the guard's wrap window with probability of about
`65 / 2^32` per input, so fuzzing the parameters will not find this bug.
