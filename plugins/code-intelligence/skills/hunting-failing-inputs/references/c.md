# C

| operation | out of range | predicate |
|---|---|---|
| `a[i]`, `*(p + k)` | UB | `index_oob(i, n)` |
| `memcpy(dst, src + off, k)` and friends | UB | `span_oob(off, k, size)`, once for `src` and once for `dst` |
| `/ 0`, `% 0` | UB, usually SIGFPE | `div_zero(y)` |
| `x << k`, `k >= width` | UB | `k >= width` |
| signed overflow | UB | `word(name, 32)` arithmetic, compared with the widened exact sum |
| `uint8_t t = a + b` | silent: the add is in `int`, then truncated on the store | 8-bit arithmetic |

Integer promotion: `a + b` on two `uint8_t` values does not wrap. It wraps
only where the result is stored to or cast to a narrow type, so put the wrap
in the model exactly there.

## Strict harness

Build with `-fsanitize=address,undefined -fno-sanitize-recover=all -g`. Pass
the input in an exact-size `malloc`, because ASan misses an overrun into slack
inside a larger buffer. If clang reports `cannot find .../libclang_rt.asan-*.a`,
install `libclang-rt-<N>-dev` or use gcc.

## Example: `examples/c/`

`parse_frame` stores `hdr + body` in a `uint8_t`, then `memcpy`s from
`b + 2 + hdr`. `model.py` should find a wrapping `hdr`/`body` pair. The plain
build of `repro.c` returns normally, and the ASan build reports a
heap-buffer-overflow at `frame.c:11`. `fuzz.c` is the libFuzzer target.
