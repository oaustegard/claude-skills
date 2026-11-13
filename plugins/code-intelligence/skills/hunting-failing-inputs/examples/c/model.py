import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'scripts'))
from z3traps import *
n, base = harness(max_len=64)
hdr, body = byte_at('hdr'), byte_at('body')
base += [n >= 2]
total = hdr + body                              # uint8_t + uint8_t, stored back to uint8_t: wraps
base += [Not(widen(total) + 2 > n)]             # passed the guard
solve_traps(base, {
    'frame.c:11 memcpy(out, b+2+hdr, body)': span_oob(2 + widen(hdr), widen(body), n),
}, show=(n, hdr, body))
