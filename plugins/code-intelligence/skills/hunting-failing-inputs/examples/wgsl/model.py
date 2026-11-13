import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'scripts'))
from z3traps import *
from z3 import UGT, UGE, ULT
off, stride, count, i = (word(n, 32) for n in ('offset', 'stride', 'count', 'i'))
N_SRC, N_DST = 64, 64                          # harness: buffer sizes in u32 elements
base = [ULT(i, count),                          # passed: i >= P.count returns
        Not(UGT(off + count * stride, N_SRC)),  # passed: guard (u32 arithmetic wraps)
        ULT(count, 65)]                         # harness: one 64-wide dispatch, plus a spare
solve_traps(base, {
    'gather.wgsl:11 src[offset + i*stride]': UGE(off + i * stride, N_SRC),
    'gather.wgsl:11 dst[i]':                 UGE(i, N_DST),
}, show=(off, stride, count, i))
