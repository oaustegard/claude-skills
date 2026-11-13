import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'scripts'))
from z3traps import *

n, base = harness(max_len=64)
b0, b1 = byte_at('b0'), byte_at('b1')        # hdrLen, bodyLen (uint8)
base += [n >= 2]                              # passed: if len(b) < 2 { return }
total = b0 + b1                               # uint8 + uint8: wraps at 256
base += [Not(widen(total) + 2 > n)]          # passed: if int(total)+2 > len(b) { return }
h, bl = widen(b0), widen(b1)
end = 2 + h + bl                              # computed in int: does not wrap
solve_traps(base, {
    'parse.go:14 b[2:2+hdrLen]':      go_slice_oob(BitVecVal(2, 64), 2 + h, n),
    'parse.go:16 b[2+hdrLen:endBody]': go_slice_oob(2 + h, end, n),
}, show=(n, b0, b1), in_order=True)
