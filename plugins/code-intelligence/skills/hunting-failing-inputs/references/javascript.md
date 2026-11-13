# JavaScript and TypeScript

Reference for step 3 (model) and step 5 (strict harness) of the procedure.

## What each trap does on failure

| operation | out of range | model with |
|---|---|---|
| `a[i]` read, Array or TypedArray | **silent**: `undefined`, which becomes `NaN` in arithmetic and `0` under bitwise ops | `index_oob(i, n)` |
| `ta[i] = v` on a TypedArray | **silent**: write dropped | `index_oob(i, n)` |
| `a[i] = v` on an Array | **silent**: the array grows, leaving holes | `index_oob(i, n)` |
| `slice`, `subarray` with `end > length` | **silent**: clamped | `slice_truncates(lo, hi, n)` |
| `DataView.getUint32(off)` etc. | `RangeError` | `span_oob(off, 4, n)` |
| `x / 0`, `x % 0` | **silent**: `Infinity` / `NaN` | `div_zero(y)` |
| `x \| 0`, `x >>> 0`, `<<`, `&` | **silent**: 32-bit truncation; shift count taken mod 32 | `js_int32(x)`, `js_uint32(x)` |
| `Uint8Array` element store | **silent**: wraps mod 256 (`Uint8ClampedArray` clamps) | `word(name, 8)` |

Plain numbers are doubles. Integers stay exact up to 2^53, so model them as
64-bit values unless a bitwise operator truncates them.

`list_traps.py` marks every `a[i]` as `silent` and cannot tell an array from an
object keyed by a variable. Drop the object lookups by reading the code.

## Strict harness

```js
import { strict } from "./strict.mjs";     // scripts/strict.mjs
decode(strict(bytes));                      // Array or any TypedArray
```

Reads and writes outside `[0, length)` throw `StrictAccessError`, and so do
`slice` or `subarray` calls with an end past the length. Arrays the function
creates internally are not covered.

With fast-check: `fc.assert(fc.property(fc.uint8Array({maxLength: 64}), (u) => { decode(strict(u)); }))`.

## Worked example: `examples/javascript/`

`decodeSamples` reads `count` 16-bit samples placed `stride` bytes apart, and
checks `2 + count*stride <= length`. That check forgets that the last sample
needs two bytes. `model.py` finds `count=62, stride=1, len=64` for `u8[p + 1]`.
It also finds a bug that was not planted: `stride=0, count=95, len=2` passes
the check and reads `u8[2]`.

Random testing, 200,000 inputs of 0–64 bytes each: plain found nothing, and
`strict(u8)` found the bug after 4,413 inputs.

*Diagnosed 2026-11-13.* The first random-testing run used a hand-written LCG,
`seed * 1103515245`, which loses precision once the product passes 2^53. The
inputs it produced never hit either bug, even with `strict`. A generator built
on `Math.imul` (mulberry32) fixed it. Do not judge a harness with a broken
random source.
