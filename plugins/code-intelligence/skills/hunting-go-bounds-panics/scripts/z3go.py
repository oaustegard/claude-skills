"""Helpers for writing Z3 path models of Go bounds checks.

Import from a model script:
    import sys; sys.path.insert(0, '<skill>/scripts')
    from z3go import *

Go semantics encoded here (all indices are 64-bit signed `int`):
    s[i]        panics unless 0 <= i < len(s)
    s[lo:hi]    panics unless 0 <= lo <= hi <= cap(s)   (cap, not len)
    s[lo:hi:mx] panics unless 0 <= lo <= hi <= mx <= cap(s)
The harness the reproducer uses is a fresh slice with cap == len, so models
use one variable for both.
"""
from z3 import (BitVec, BitVecs, BitVecVal, BoolVal, If, Not, Or, And, Solver,
                ZeroExt, SignExt, Extract, sat, unsat, unknown)

W = 64  # Go int on 64-bit targets

def harness(max_len=64, min_len=0):
    """Symbolic len(b) == cap(b) for a fresh input slice, bounded."""
    n = BitVec('len', W)
    return n, [n >= min_len, n <= max_len]

def byte_at(name):
    """One symbolic input byte (uint8)."""
    return BitVec(name, 8)

def to_int(x, signed=False):
    """Go conversion int(x) from a narrower integer: uint* zero-extends,
    int* sign-extends. Arithmetic done BEFORE this call wraps at x's width,
    which is the bug class this skill exists for."""
    k = W - x.size()
    if k == 0:
        return x
    return SignExt(k, x) if signed else ZeroExt(k, x)

def index_oob(i, length):
    """True when s[i] panics."""
    return Or(i < 0, i >= length)

def slice_oob(lo, hi, cap, mx=None):
    """True when s[lo:hi] (or s[lo:hi:mx]) panics."""
    if mx is None:
        return Or(lo < 0, hi < lo, hi > cap)
    return Or(lo < 0, hi < lo, mx < hi, mx > cap)

def solve_traps(base, traps, show=(), in_order=False):
    """One solver per trap, so a sat on one never hides another.

    base:     list of path constraints shared by every trap (harness, guards)
    traps:    {label: panic_condition}, in program order
    show:     z3 terms to print from each model
    in_order: add Not(every earlier trap) to each query. Use it when the traps
              sit on one straight-line path: a later check is reached only if
              the earlier ones passed. Without it a sat on trap 2 can be an
              input that really panics at trap 1. Leave it off when traps sit
              on different branches: negating a check that is not on the path
              over-constrains the query and can turn a real sat into unsat.
    Returns {label: model or None}. Prints sat/unsat/unknown per trap.
    unknown is reported, never folded into unsat.
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
        if r == sat:
            m = s.model()
            out[label] = m
            for t in show:
                print(f'    {t} = {m.eval(t, model_completion=True)}')
        else:
            out[label] = None
            if r == unknown:
                print(f'    reason: {s.reason_unknown()}')
    return out

def concrete_bytes(model, byte_vars, length=None):
    """Assemble input bytes from a model; unconstrained bytes become 0."""
    vals = [model.eval(b, model_completion=True).as_long() for b in byte_vars]
    if length is not None:
        vals = (vals + [0] * length)[:length]
    return bytes(vals)

def go_literal(bs):
    """Render bytes as a Go []byte literal for a reproducer test."""
    return '[]byte{' + ', '.join(f'0x{b:02x}' for b in bs) + '}'
