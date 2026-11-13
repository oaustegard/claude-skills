import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'scripts'))
from z3traps import *
L, base = harness(max_len=64)
b0, b1 = byte_at('b0'), byte_at('b1')
base += [L >= 2]                              # passed: len(b) < 2
n, m = widen(b0), widen(b1)                   # Python ints never wrap
base += [Not(L < 2 + n + m)]                  # passed: len(b) < 2+n+m
k = 2 + n + m
r = solve_traps(base, {
    'record.py:8 b[2:2+n]':     slice_truncates(BitVecVal(2, 64), 2 + n, L),
    'record.py:9 b[2+n:2+n+m]': slice_truncates(2 + n, k, L),
    'record.py:10 b[k:k+2]':    slice_truncates(k, k + 2, L),
}, show=(L, b0, b1))
m10 = r['record.py:10 b[k:k+2]']
print('reproducer:', literal(concrete_bytes(m10, [b0, b1], value(m10, L)), 'python'))
