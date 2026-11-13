import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'scripts'))
from z3traps import *

# The loop advances i by 1 or 2, so unroll it per concrete length L.
for L in range(1, 17):
    s = [byte_at(f's{k}') for k in range(L)]
    i, live = BitVecVal(1, 64), BoolVal(True)
    idx_traps = []
    for _ in range(L + 1):                    # at most L iterations
        enter = And(live, i < L)
        idx_traps.append(And(live, i < L, index_oob(i, L)))   # s[i] in the loop condition
        cur = BitVecVal(0, 8)
        for k in range(L):
            cur = If(i == k, s[k], cur)
        cont = And(enter, cur != ord('"'))
        i = If(cont, i + If(cur == ord('\\'), BitVecVal(2, 64), BitVecVal(1, 64)), i)
        live = cont
    base = [s[0] == ord('"')]                 # passed: s[0] != '"' returns nil
    r = solve_traps(base, {
        f'L={L} parse.go:27 s[i]':   Or(*idx_traps),
        f'L={L} parse.go:33 s[1:i]': go_slice_oob(BitVecVal(1, 64), i, BitVecVal(L, 64)),
    })
    m = r[f'L={L} parse.go:33 s[1:i]']
    if m:
        print('reproducer:', literal(concrete_bytes(m, s), 'go'))
        break
