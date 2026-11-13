# Python

Reference for step 3 (model) and step 5 (strict harness) of the procedure.

## What each trap does on failure

| operation | out of range | model with |
|---|---|---|
| `a[i]`, `i >= len` or `i < -len` | `IndexError` | `py_index_oob(i, n)` |
| `a[i]`, `-len <= i < 0` | **silent**: reads `a[len + i]` | `negative_index(i, n)` |
| `a[lo:hi]`, `hi > len` | **silent**: shorter result | `slice_truncates(lo, hi, n)` |
| `x / y`, `x // y`, `x % y` | `ZeroDivisionError` | `div_zero(y)` |
| `struct.unpack`, `int.from_bytes` on a short slice | `struct.error` / silently smaller int | the slice feeding it |
| `numpy` `uint8`/`int32` arithmetic | **silent** wrap (no warning for integers) | `word(name, bits)`, no `widen` until the cast |

Python `int` never wraps. Model it with `widen(byte)` to 64 bits, and keep
bounds small enough that 64 bits cannot overflow.

## Strict harness

```python
from strict import strict            # scripts/strict.py
parse(strict(data))                  # bytes, bytearray or list
```

Negative indexes and past-the-end slices on the input then raise
`StrictAccessError`, and slices stay strict as they flow through the parser.
The wrapper covers only the object you wrap. A list the function builds
itself (`out = []`) is plain, so its silent negative index still needs the
model, or a local `out = StrictList()` while testing. Code that deliberately
reads `a[-1]` needs `strict(data, allow_negative=True)`.

For Hypothesis, wrap inside the test: `@given(st.binary(max_size=64))` then
`parse(strict(b))`.

## Worked example: `examples/python/`

`record.py` has two planted bugs:

- `parse_record` checks `len(b) < 2 + n + m` and forgets the two CRC bytes.
  The CRC slice comes back short, and `int.from_bytes` turns it into a wrong
  number without an error.
- `lz_decode` copies from `len(out) - dist` with no `dist <= len(out)` check.

`model_record.py` reports lines 8 and 9 `unsat` and line 10 `sat`. It finds
`n=30, m=32`, `len=64`. `model_lz.py` unrolls the loop over the input length
and returns `b'\x00\x81'` at `L=2`, where `lz_decode` returns `b'\x00\x00'`
instead of raising.

Random testing, 200,000 inputs of 0–64 bytes each:

| target | plain input | `strict(input)` |
|---|---|---|
| `parse_record` | nothing | found after 1,581 inputs |
| `lz_decode` | `IndexError` after 3 inputs (the `dist > 2*len` case) | same |

The loud case of the `lz_decode` bug shows up at once, while the silent
`-len <= i < 0` case never surfaces as an error. Fixing exactly the reported
crash (rejecting `len(out) - dist < -len(out)`) would leave the silent case in
place. The model separates the two.

*Diagnosed 2026-11-13.* The first `lz_decode` model treated every negative index
as a silent wrap. The input it produced, `b'\x00\xc0'`, raised `IndexError`,
because `-64` is below `-len`. The reproducer caught the model error, and the
`negative_index(i, n)` helper now encodes `-n <= i < 0`.
