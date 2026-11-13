import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'scripts'))
from z3traps import *
L, base = harness(max_len=64)
c, s = byte_at('count'), byte_at('stride')
C, S = widen(c), widen(s)                      # JS numbers: exact for these sizes
base += [L >= 2, Not(2 + C * S > L)]           # passed both early returns
i = BitVec('i', 64)
base += [i >= 0, i < C]                        # some loop iteration
p = 2 + i * S
solve_traps(base, {
    'samples.mjs:9 u8[p]':     index_oob(p, L),
    'samples.mjs:9 u8[p + 1]': index_oob(p + 1, L),
}, show=(L, c, s, i))
