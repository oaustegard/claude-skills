import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'scripts'))
from z3traps import *
# The output length depends on the path, so unroll over input length L.
for L in range(1, 9):
    toks = [byte_at(f't{k}') for k in range(L)]
    outlen, traps = BitVecVal(0, 64), []
    for tok in toks:
        is_ref = widen(tok) >= 128           # widen first: BitVec >= is signed
        dist = widen(tok) - 127
        # reached only if out is non-empty (the raise above), so require outlen > 0
        traps.append(And(is_ref, outlen > 0, negative_index(outlen - dist, outlen)))
        outlen = outlen + 1
    r = solve_traps([], {f'L={L} record.py:24 out[len(out)-dist]': Or(*traps)})
    mdl = r[f'L={L} record.py:24 out[len(out)-dist]']
    if mdl:
        print('reproducer:', literal(concrete_bytes(mdl, toks), 'python'))
        break
