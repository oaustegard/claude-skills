# C

Reference for step 3 (model) and step 5 (strict harness) of the procedure.

## What each trap does on failure

Without sanitizers, every row is silent or a crash far from its cause.

| operation | out of range | model with |
|---|---|---|
| `a[i]`, `*(p + k)` | UB: reads or writes neighbouring memory | `index_oob(i, n)` |
| `memcpy(dst, src + off, k)` and friends | UB | `span_oob(off, k, size)`, once each for `src` and `dst` |
| `x / 0`, `x % 0` | UB, usually SIGFPE | `div_zero(y)` |
| `x << k` with `k >= width` | UB | `k >= width` |
| signed overflow | UB (UBSan reports it) | `word(name, 32)` arithmetic, then compare with the widened exact sum |
| `uint8_t t = a + b` | **silent**: computed in `int`, truncated on the store | `byte_at` arithmetic at 8 bits |

Integer promotion matters. `a + b` on two `uint8_t` values is an `int` add and
does not wrap. It wraps only where the result is stored in, or cast to, a narrow
type. Put the wrap in the model exactly where the source narrows.

## Strict harness

Build with `-fsanitize=address,undefined -fno-sanitize-recover=all -g`. Give
the function an input buffer of exactly the input's size
(`malloc(size)` + `memcpy`). ASan's redzones catch a one-byte overrun on a heap
block, but not an overrun into slack inside a larger buffer.

If clang fails to link with
`cannot find .../libclang_rt.asan-x86_64.a`, the compiler-rt runtime is
missing. Install `libclang-rt-<N>-dev`, or use gcc, which ships libasan.

## Worked example: `examples/c/`

`parse_frame` stores `hdr + body` in a `uint8_t`, then `memcpy`s `body` bytes
from `b + 2 + hdr`. `model.py` finds `len=64, hdr=127, body=191`, which wraps
`total` to 62.

| run | result |
|---|---|
| `repro.c`, plain build | returns 191 and exits 0: an overread with no symptom |
| `repro.c`, gcc ASan+UBSan | `heap-buffer-overflow ... READ of size 191`, `frame.c:11` |
| libFuzzer, no ASan, 30 s | 77,234,678 runs, nothing found |
| libFuzzer + ASan, 30 s | found within about 250 runs |

The fuzzer needed the sanitizer, and the model needed neither.
