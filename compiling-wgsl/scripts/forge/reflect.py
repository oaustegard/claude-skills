"""Binding reflection and WGSL host-shareable memory layout, for the differential tests.

``bindings(module)`` lists every @group/@binding resource. ``fill(type)`` produces a
byte buffer for a buffer-typed binding with plausible random values per field (small
non-negative integers, floats in [-4, 4]), so integer fields used as indices stay mostly
in range and float math stays finite.
"""
from __future__ import annotations

import struct

import numpy as np

from .ast import Decl, Ident, Lit, Struct
from .scope import resolve

RUNTIME_ARRAY_LEN = 256


def _round(n, a):
    return (n + a - 1) // a * a


class Layout:
    def __init__(self, module):
        resolve(module)
        self.structs = {d.name: d for d in module.decls if isinstance(d, Struct)}
        self.aliases = {d.name: d.type for d in module.decls if type(d).__name__ == "Alias"}
        self.consts = {d.name: d.init for d in module.decls if isinstance(d, Decl) and d.kind == "const"}

    def resolve_alias(self, t: Ident) -> Ident:
        while t.name in self.aliases and not t.tmpl:
            t = self.aliases[t.name]
        return t

    def count(self, e) -> int:
        if isinstance(e, Lit):
            return int(e.text.rstrip("iu"), 0)
        if isinstance(e, Ident) and e.name in self.consts:
            return self.count(self.consts[e.name])
        raise ValueError(f"cannot evaluate array count {e!r}")

    def scalar(self, t: Ident):
        name = t.name
        short = {"f": "f32", "i": "i32", "u": "u32", "h": "f16"}
        if name in ("f32", "i32", "u32", "f16"):
            return name, None
        if name.startswith("vec"):
            n = int(name[3])
            comp = short[name[4]] if len(name) == 5 else self.resolve_alias(t.tmpl[0]).name
            return comp, ("vec", n)
        if name.startswith("mat"):
            c, r = int(name[3]), int(name[5])
            comp = short[name[6]] if len(name) == 7 else self.resolve_alias(t.tmpl[0]).name
            return comp, ("mat", c, r)
        return None, None

    def size_align(self, t: Ident):
        t = self.resolve_alias(t)
        if t.name == "atomic":
            return self.size_align(t.tmpl[0])
        comp, shape = self.scalar(t)
        if comp is not None:
            s = 2 if comp == "f16" else 4
            if shape is None:
                return s, s
            if shape[0] == "vec":
                n = shape[1]
                return n * s, (2 if n == 2 else 4) * s
            c, r = shape[1], shape[2]
            va = (2 if r == 2 else 4) * s
            return c * _round(r * s, va), va
        if t.name == "array":
            es, ea = self.size_align(t.tmpl[0])
            stride = _round(es, ea)
            n = self.count(t.tmpl[1]) if len(t.tmpl) > 1 else RUNTIME_ARRAY_LEN
            return n * stride, ea
        if t.name in self.structs:
            off, align = 0, 1
            for m in self.structs[t.name].members:
                s, a = self.size_align(m.type)
                for at in m.attrs:
                    if at.name == "align":
                        a = self.count(at.args[0])
                    if at.name == "size":
                        s = self.count(at.args[0])
                off = _round(off, a) + s
                align = max(align, a)
            return _round(off, align), align
        raise ValueError(f"not host-shareable: {t.name}")

    def fill(self, t: Ident, rng) -> bytes:
        size, _ = self.size_align(t)
        buf = bytearray(size)
        self._fill(t, 0, buf, rng)
        return bytes(buf)

    def _fill(self, t, off, buf, rng):
        t = self.resolve_alias(t)
        if t.name == "atomic":
            return self._fill(t.tmpl[0], off, buf, rng)
        comp, shape = self.scalar(t)
        if comp is not None:
            s = 2 if comp == "f16" else 4
            if shape is None:
                n_cols, rows, va = 1, 1, s
            elif shape[0] == "vec":
                n_cols, rows, va = 1, shape[1], s
            else:
                n_cols, rows = shape[1], shape[2]
                va = _round(rows * s, (2 if rows == 2 else 4) * s)
            for c in range(n_cols):
                for r in range(rows):
                    o = off + c * va + r * s
                    if comp == "f32":
                        struct.pack_into("<f", buf, o, float(np.float32(rng.uniform(-4, 4))))
                    elif comp == "f16":
                        buf[o:o + 2] = np.float16(rng.uniform(-4, 4)).tobytes()
                    else:
                        struct.pack_into("<I", buf, o, int(rng.integers(0, 16)))
            return
        if t.name == "array":
            es, ea = self.size_align(t.tmpl[0])
            stride = _round(es, ea)
            n = self.count(t.tmpl[1]) if len(t.tmpl) > 1 else RUNTIME_ARRAY_LEN
            for k in range(n):
                self._fill(t.tmpl[0], off + k * stride, buf, rng)
            return
        if t.name in self.structs:
            o = 0
            for m in self.structs[t.name].members:
                s, a = self.size_align(m.type)
                for at in m.attrs:
                    if at.name == "align":
                        a = self.count(at.args[0])
                    if at.name == "size":
                        s = self.count(at.args[0])
                o = _round(o, a)
                self._fill(m.type, off + o, buf, rng)
                o += s


def bindings(module):
    """[(group, binding, decl)] for every resource variable."""
    out = []
    lay = Layout(module)
    for d in module.decls:
        if not isinstance(d, Decl) or d.kind != "var":
            continue
        g = b = None
        for a in d.attrs:
            if a.name == "group":
                g = lay.count(a.args[0])
            if a.name == "binding":
                b = lay.count(a.args[0])
        if g is not None and b is not None:
            out.append((g, b, d))
    return out, lay


def buffer_type(decl):
    """'uniform' | 'storage' | 'read-only-storage' | None (textures, samplers...)."""
    if not decl.tmpl:
        return None
    space = decl.tmpl[0].name
    if space == "uniform":
        return "uniform"
    if space == "storage":
        access = decl.tmpl[1].name if len(decl.tmpl) > 1 else "read"
        return "storage" if access == "read_write" else "read-only-storage"
    return None
