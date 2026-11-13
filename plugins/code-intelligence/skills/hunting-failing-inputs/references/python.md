# Python

| operation | out of range | predicate |
|---|---|---|
| `a[i]`, `i >= len` or `i < -len` | `IndexError` | `py_index_oob(i, n)` |
| `a[i]`, `-len <= i < 0` | silent: reads `a[len + i]` | `negative_index(i, n)` |
| `a[lo:hi]`, `hi > len` | silent: shorter result | `slice_truncates(lo, hi, n)` |
| `/`, `//`, `%` | `ZeroDivisionError` | `div_zero(y)` |
| `struct.unpack`, `int.from_bytes` | `struct.error`, or silently a smaller int | model the slice that feeds it |
| numpy `uint8`/`int32` arithmetic | silent wrap | `word(name, bits)`, `widen` only at the cast |

Python `int` never wraps: `widen(byte)` to 64 bits, and keep bounds small enough
that 64 bits cannot overflow.

## Strict harness

```python
from strict import strict      # scripts/strict.py
parse(strict(data))            # bytes, bytearray or list
```

Negative indexes and past-the-end slices on the wrapped input raise
`StrictAccessError`, and slices stay strict. Lists the function builds itself
are not covered: wrap them while testing (`out = StrictList()`) or rely on the
model. Code that reads `a[-1]` on purpose needs `strict(data, allow_negative=True)`.
For Hypothesis, call `parse(strict(b))` inside the test.

## Example: `examples/python/`

- `record.py` `parse_record`: the length check forgets the 2 CRC bytes, so
  `int.from_bytes` gets a short slice. `model_record.py` should report lines 8
  and 9 `unsat` and line 10 `sat`.
- `record.py` `lz_decode`: a back-reference has no `dist <= len(out)` check.
  `model_lz.py` unrolls over the input length.
