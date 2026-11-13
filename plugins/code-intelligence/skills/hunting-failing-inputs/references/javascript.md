# JavaScript and TypeScript

| operation | out of range | predicate |
|---|---|---|
| `a[i]` read | silent: `undefined`, which becomes `NaN` (or `0` under bitwise ops) | `index_oob(i, n)` |
| `ta[i] = v` on a TypedArray | silent: the write is dropped | `index_oob(i, n)` |
| `a[i] = v` on an Array | silent: the array grows, with holes | `index_oob(i, n)` |
| `slice`, `subarray` past the end | silent: clamped | `slice_truncates(lo, hi, n)` |
| `DataView.getUint32(off)` etc. | `RangeError` | `span_oob(off, 4, n)` |
| `/ 0`, `% 0` | silent: `Infinity` or `NaN` | `div_zero(y)` |
| `\|0`, `>>>0`, `<<`, `&` | silent: 32-bit truncation; shift count mod 32 | `js_int32`, `js_uint32` |
| `Uint8Array` store | silent: wraps mod 256 | `word(name, 8)` |

Numbers are doubles and exact up to 2^53, so model them at 64 bits unless a
bitwise operator truncates. `list_traps.py` cannot tell `a[i]` on an array from
an object lookup, so strike the lookups by reading the code.

## Strict harness

```js
import { strict } from "./strict.mjs";   // scripts/strict.mjs
decode(strict(u8));                       // Array or any TypedArray
```

Reads and writes outside `[0, length)`, and `slice` or `subarray` calls that
run past the end, throw `StrictAccessError`. Arrays the function creates itself
are not covered. With fast-check, call `decode(strict(u))` inside the property.

## Example: `examples/javascript/`

`decodeSamples` checks `2 + count*stride <= length` and forgets that each
sample is 2 bytes. `model.py` should find both `u8[p + 1]` and the
`stride = 0` case. `samples.test.mjs` replays both inside `strict`.

On 2026-11-13, random testing with an LCG that lost precision past 2^53 never
hit the bug. Use a `Math.imul`-based generator.
