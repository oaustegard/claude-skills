"""A partial WGSL type inference, enough to know when an explicit type is redundant.

``infer(expr)`` returns a canonical type string such as ``"f32"``, ``"vec3<f32>"``,
``"mat4x4<f32>"`` or a struct name, ``"AInt"``/``"AFloat"`` for abstract literals, or None
when it cannot tell. None always means "keep the annotation": every caller treats an
unknown type as a reason not to transform.
"""
from __future__ import annotations

import re

from .ast import Binary, Call, Decl, Ident, Index, Lit, Member, Param, Unary
from .names import is_swizzle

_SCALARS = {"bool", "f16", "f32", "i32", "u32", "i64", "u64", "AInt", "AFloat"}
_ALIAS = {f"vec{n}{s}": f"vec{n}<{t}>" for n in (2, 3, 4)
          for s, t in (("i", "i32"), ("u", "u32"), ("f", "f32"), ("h", "f16"))}
_ALIAS.update({f"mat{c}x{r}{s}": f"mat{c}x{r}<{t}>" for c in (2, 3, 4) for r in (2, 3, 4)
               for s, t in (("f", "f32"), ("h", "f16"))})

# builtins whose result has the type of (the join of) the listed argument positions
_SAME_AS = {
    **{f: None for f in """abs acos acosh asin asinh atan atanh ceil cos cosh degrees exp exp2
    floor fract inverseSqrt log log2 normalize radians round saturate sign sin sinh sqrt tan
    tanh trunc min max clamp fma dpdx dpdxCoarse dpdxFine dpdy dpdyCoarse dpdyFine fwidth
    fwidthCoarse fwidthFine countLeadingZeros countOneBits countTrailingZeros reverseBits
    firstLeadingBit firstTrailingBit quantizeToF16""".split()},
    "mix": (0, 1), "smoothstep": (2,), "step": (1,), "pow": (0, 1), "atan2": (0, 1),
    "reflect": (0, 1), "refract": (0,), "cross": (0, 1), "select": (0, 1), "faceForward": (0,),
    "ldexp": (0,), "extractBits": (0,), "insertBits": (0, 1),
}
_SCALAR_OF = {"length": 0, "distance": 0, "dot": 0}


def canon(ty) -> str | None:
    """Canonical text of a type expression (Ident with template args)."""
    if ty is None:
        return None
    if isinstance(ty, str):
        return ty
    if not isinstance(ty, Ident):
        return None
    if ty.sym is not None:
        if ty.sym.kind == "alias":
            return canon(ty.sym.node.type)
        if ty.sym.kind == "struct":
            return "struct:" + ty.sym.node.name
        return None
    if ty.name in _ALIAS and not ty.tmpl:
        return _ALIAS[ty.name]
    if not ty.tmpl:
        return ty.name
    args = []
    for a in ty.tmpl:
        if isinstance(a, Lit):
            args.append(a.text.rstrip("iu"))
        else:
            c = canon(a)
            if c is None:
                return None
            args.append(c)
    return f"{ty.name}<{','.join(args)}>"


def _parts(t):
    """('scalar', c) | ('vec', n, c) | ('mat', c, r, comp) | None."""
    if t in _SCALARS:
        return ("scalar", t)
    m = re.fullmatch(r"vec([234])<(\w+)>", t or "")
    if m:
        return ("vec", int(m.group(1)), m.group(2))
    m = re.fullmatch(r"mat([234])x([234])<(\w+)>", t or "")
    if m:
        return ("mat", int(m.group(1)), int(m.group(2)), m.group(3))
    return None


def _join_scalar(a, b):
    if a == b:
        return a
    abstract = {"AInt": 0, "AFloat": 1}
    if a in abstract and b in abstract:
        return "AFloat"
    if a in abstract:
        if a == "AFloat" and b in ("i32", "u32", "i64", "u64"):
            return None
        return b
    if b in abstract:
        if b == "AFloat" and a in ("i32", "u32", "i64", "u64"):
            return None
        return a
    return None


def join(a, b):
    if a is None or b is None:
        return None
    pa, pb = _parts(a), _parts(b)
    if pa is None or pb is None:
        return a if a == b else None
    ca, cb = pa[-1], pb[-1]
    c = _join_scalar(ca, cb)
    if c is None:
        return None
    if pa[0] == "scalar" and pb[0] == "scalar":
        return c
    if pa[0] == "vec" and pb[0] == "vec":
        return f"vec{pa[1]}<{c}>" if pa[1] == pb[1] else None
    if pa[0] == "vec" and pb[0] == "scalar":
        return f"vec{pa[1]}<{c}>"
    if pb[0] == "vec" and pa[0] == "scalar":
        return f"vec{pb[1]}<{c}>"
    return None


def concretize(t):
    if t is None:
        return None
    return t.replace("AFloat", "f32").replace("AInt", "i32")


def lit_type(text):
    if text in ("true", "false"):
        return "bool"
    if text.endswith("li"):
        return "i64"
    if text.endswith("lu"):
        return "u64"
    is_hex = text.lower().startswith("0x")
    last = text[-1]
    if last == "f" and not is_hex:
        return "f32"
    if last == "h":
        return "f16"
    if is_hex:
        if "p" in text.lower() or "." in text:
            return "f32" if last == "f" else "AFloat"
        return {"i": "i32", "u": "u32"}.get(last, "AInt")
    if last == "i":
        return "i32"
    if last == "u":
        return "u32"
    if "." in text or "e" in text.lower():
        return "AFloat"
    return "AInt"


def sym_type(sym):
    if sym.type_cache is not None:
        return sym.type_cache or None
    node = sym.node
    t = None
    if isinstance(node, (Param,)):
        t = canon(node.type)
    elif isinstance(node, Decl):
        if node.type is not None:
            t = canon(node.type)
        elif node.init is not None:
            sym.type_cache = ""          # break cycles
            t = infer(node.init)
            if node.kind in ("let", "var", "override"):
                t = concretize(t)
    sym.type_cache = t or ""
    return t


def _ptr_inner(t):
    m = re.fullmatch(r"ptr<(\w+),(.+?)(?:,(\w+))?>", t or "")
    return m.group(2) if m else None


def infer(e):
    if isinstance(e, Lit):
        return lit_type(e.text)
    if isinstance(e, Ident):
        if e.sym is None:
            return None
        if e.sym.kind in ("var", "let", "const", "override", "param"):
            return sym_type(e.sym)
        return None
    if isinstance(e, Call):
        return _infer_call(e)
    if isinstance(e, Unary):
        t = infer(e.expr)
        if e.op in ("-", "~", "!"):
            return t
        if e.op == "*":
            return _ptr_inner(t)
        return None
    if isinstance(e, Binary):
        return _infer_binary(e)
    if isinstance(e, Member):
        t = infer(e.expr)
        p = _parts(t)
        if p and p[0] == "vec" and is_swizzle(e.name):
            return p[2] if len(e.name) == 1 else f"vec{len(e.name)}<{p[2]}>"
        if t and t.startswith("struct:"):
            from .ast import Struct
            return _struct_member_type(t[7:], e.name, e)
        return None
    if isinstance(e, Index):
        t = infer(e.expr)
        p = _parts(t)
        if p and p[0] == "vec":
            return p[2]
        if p and p[0] == "mat":
            return f"vec{p[2]}<{p[3]}>"
        m = re.fullmatch(r"array<(.+?)(?:,\w+)?>", t or "")
        if m:
            return m.group(1)
        return None
    return None


_STRUCTS = {}


def register_structs(module):
    from .ast import Struct
    _STRUCTS.clear()
    for d in module.decls:
        if isinstance(d, Struct):
            _STRUCTS[d.name] = d


def _struct_member_type(sname, mname, e):
    st = _STRUCTS.get(sname)
    if st is None:
        return None
    for m in st.members:
        if m.name == mname:
            return canon(m.type)
    return None


def _infer_call(e: Call):
    c = e.callee
    if c.sym is not None:
        if c.sym.kind == "fn":
            return canon(c.sym.node.ret) if c.sym.node.ret is not None else None
        if c.sym.kind in ("struct", "alias"):
            return canon(c)
        return None
    name = c.name
    if c.tmpl or name in _ALIAS:
        t = canon(c)
        if t and (_parts(t) or t.startswith("array<")):
            return t
        return None
    if name in ("f32", "i32", "u32", "f16", "bool", "i64", "u64"):
        return name
    if name in ("vec2", "vec3", "vec4") and e.args:
        comp = None
        for a in e.args:
            t = infer(a)
            p = _parts(t)
            if p is None:
                return None
            comp = p[-1] if comp is None else _join_scalar(comp, p[-1])
            if comp is None:
                return None
        return f"{name}<{comp}>"
    if name in _SAME_AS:
        pos = _SAME_AS[name]
        idx = range(len(e.args)) if pos is None else [k for k in pos if k < len(e.args)]
        if name == "select":
            idx = [0, 1]
        t = None
        for k in idx:
            tk = infer(e.args[k])
            t = tk if t is None else join(t, tk)
            if t is None:
                return None
        return t
    if name in _SCALAR_OF and e.args:
        p = _parts(infer(e.args[0]))
        return p[-1] if p else None
    return None


def _infer_binary(e: Binary):
    op = e.op
    if op in ("&&", "||"):
        return "bool"
    lt, rt = infer(e.left), infer(e.right)
    if op in ("==", "!=", "<", ">", "<=", ">="):
        p = _parts(lt) or _parts(rt)
        if p and p[0] == "vec":
            return f"vec{p[1]}<bool>"
        return "bool" if p else None
    if op in ("<<", ">>"):
        return lt
    if lt is None or rt is None:
        return None
    pl, pr = _parts(lt), _parts(rt)
    if op == "*" and pl and pr:
        if pl[0] == "mat" and pr[0] == "vec":
            c = _join_scalar(pl[3], pr[2])
            return f"vec{pl[2]}<{c}>" if c else None
        if pl[0] == "vec" and pr[0] == "mat":
            c = _join_scalar(pl[2], pr[3])
            return f"vec{pr[1]}<{c}>" if c else None
        if pl[0] == "mat" and pr[0] == "mat":
            c = _join_scalar(pl[3], pr[3])
            return f"mat{pr[1]}x{pl[2]}<{c}>" if c else None
        if pl[0] == "mat" and pr[0] == "scalar":
            c = _join_scalar(pl[3], pr[1])
            return f"mat{pl[1]}x{pl[2]}<{c}>" if c else None
        if pr[0] == "mat" and pl[0] == "scalar":
            c = _join_scalar(pr[3], pl[1])
            return f"mat{pr[1]}x{pr[2]}<{c}>" if c else None
    return join(lt, rt)
