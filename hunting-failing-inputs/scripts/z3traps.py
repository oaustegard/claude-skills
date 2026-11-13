"""Helpers for writing Z3 path models of traps, for several languages.

Import from a model script:
    import sys; sys.path.insert(0, '<skill>/scripts')
    from z3traps import *

Every value is a Z3 bit-vector. Indices, lengths and Python or JS integers
are 64-bit signed (enough for any input this skill bounds to a few hundred
bytes). Fixed-width types get their own width, so that arithmetic wraps where
the language wraps: uint8_t, u32, Uint8Array elements, Go's uint8, JS `|0`.

Trap predicates are True when the operation fails:
    index_oob(i, n)            a[i]: JS, C, WGSL, Go          i < 0 or i >= n
    py_index_oob(i, n)         Python a[i] raises             i < -n or i >= n
    negative_index(i, n)       Python a[i] silently reads from the end (-n <= i < 0)
    slice_truncates(lo, hi, n) Python/JS slice comes back short
    go_slice_oob(lo, hi, cap)  Go s[lo:hi] panics (cap, not len)
    span_oob(off, k, size)     C memcpy(dst, buf+off, k) or a k-byte read at off
    div_zero(d)                any division or modulo
"""
from z3 import (BitVec, BitVecVal, BoolVal, If, Not, Or, And, Solver, ZeroExt,
                SignExt, Extract, sat, unknown)

W = 64


def harness(max_len: int = 64, min_len: int = 0, name: str = 'len'):
    """Symbolic input length, bounded. Returns (n, constraints)."""
    n = BitVec(name, W)
    return n, [n >= min_len, n <= max_len]


def byte_at(name: str):
    """One symbolic input byte (unsigned 8-bit)."""
    return BitVec(name, 8)


def word(name: str, bits: int):
    """A symbolic fixed-width integer: u16/u32 fields, WGSL u32 params."""
    return BitVec(name, bits)


def widen(x, signed: bool = False, to: int = W):
    """Convert to a wider integer, the way a cast or promotion does.
    Arithmetic done BEFORE this call wraps at x's width."""
    k = to - x.size()
    if k <= 0:
        return x
    return SignExt(k, x) if signed else ZeroExt(k, x)


def js_int32(x):
    """JS `x | 0`: keep the low 32 bits, read them as signed."""
    return SignExt(W - 32, Extract(31, 0, x))


def js_uint32(x):
    """JS `x >>> 0`: keep the low 32 bits, read them as unsigned."""
    return ZeroExt(W - 32, Extract(31, 0, x))


def index_oob(i, n):
    return Or(i < 0, i >= n)


def py_index_oob(i, n):
    return Or(i < -n, i >= n)


def negative_index(i, n):
    """Python a[i] with -n <= i < 0: no error, reads a[n + i]. Below -n it raises
    instead, which py_index_oob covers."""
    return And(i < 0, i >= -n)


def slice_truncates(lo, hi, n):
    """a[lo:hi] (Python) or a.slice(lo, hi) / subarray (JS) returns fewer than
    hi - lo items. Assumes lo, hi >= 0; negative bounds count from the end."""
    return And(hi > lo, hi > n)


def go_slice_oob(lo, hi, cap, mx=None):
    if mx is None:
        return Or(lo < 0, hi < lo, hi > cap)
    return Or(lo < 0, hi < lo, mx < hi, mx > cap)


def span_oob(off, k, size):
    """A k-byte access starting at off overruns a size-byte buffer."""
    return Or(off < 0, k < 0, off + k > size)


def div_zero(d):
    return d == 0


def solve_traps(base, traps, show=(), in_order=False):
    """One solver per trap, so a sat on one never hides another.

    base:     constraints shared by every trap (harness bounds, passed guards)
    traps:    {label: failure_condition}, in program order
    show:     z3 terms to print from each model
    in_order: add Not(every earlier trap) to each query. Use it when the
              traps sit on one straight-line path: a later trap is reached
              only if the earlier ones passed. Leave it off when traps sit on
              different branches, where negating a trap that is not on the
              path over-constrains the query and can turn a real sat to unsat.
    Returns {label: model or None}. unknown is printed, never folded into unsat.
    """
    out, earlier = {}, []
    for label, cond in traps.items():
        s = Solver()
        s.set('timeout', 30_000)
        s.add(*base)
        if in_order:
            s.add(*[Not(c) for c in earlier])
        earlier.append(cond)
        s.add(cond)
        r = s.check()
        print(f'{label}: {r}')
        out[label] = None
        if r == sat:
            m = s.model()
            out[label] = m
            for t in show:
                print(f'    {t} = {m.eval(t, model_completion=True)}')
        elif r == unknown:
            print(f'    reason: {s.reason_unknown()}')
    return out


def value(model, term) -> int:
    """Concrete int for a term; unconstrained terms become 0."""
    return model.eval(term, model_completion=True).as_long()


def concrete_bytes(model, byte_vars, length: int | None = None) -> bytes:
    """Assemble input bytes from a model; unconstrained bytes become 0."""
    vals = [value(model, b) for b in byte_vars]
    if length is not None:
        vals = (vals + [0] * length)[:length]
    return bytes(vals)


def literal(bs: bytes, lang: str) -> str:
    """Render bytes as a literal for a reproducer test."""
    hexes = ', '.join(f'0x{b:02x}' for b in bs)
    return {
        'python': repr(bytes(bs)),
        'javascript': f'Uint8Array.of({hexes})',
        'c': f'{{{hexes}}}',
        'go': f'[]byte{{{hexes}}}',
        'wgsl': f'array<u32, {len(bs)}>({", ".join(f"{b}u" for b in bs)})',
    }[lang]
