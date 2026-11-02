"""WGSL minifier: AST passes that shrink a module without changing what it computes.

Passes, in order (each can be switched off through ``Options``):

  dce        drop module-scope declarations no entry point reaches, then unused
             function-scope let/const/var whose initialiser has no side effects
  inline     replace a module-scope ``const`` holding a single literal by the literal,
             where that is shorter overall
  rewrite    ``x = x op y`` -> ``x op= y``; ``x += 1`` -> ``x++`` on integers; drop a
             trailing bare ``return;``, empty statements and empty ``else {}``
  untype     drop ``: T`` from let/var when the initialiser's inferred type is exactly T
  literals   shortest spelling of every number that denotes the same value and type
  aliases    ``vec3<f32>`` -> ``vec3f`` and the other predeclared aliases
  rename     scope-aware renaming, most-referenced names first, struct members included

What it never touches: entry-point names, ``override`` names (the host sets them by
name), ``@group/@binding`` numbers, ``@location`` / ``@builtin`` / ``@id`` attributes,
directives, and member names that look like swizzles (``x``, ``rgb``).
"""
from __future__ import annotations

import copy
import math
import re
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from .ast import (
    Assign, Block, Call, ConstAssert, Decl, Empty, For, Fn, Ident, If, IncDec, Index, Lit,
    Loop, Member, Module, Return, Struct, Switch, Unary, Binary, While, walk,
)
from .names import BUILTIN_MEMBERS, FORBIDDEN, is_swizzle, name_stream
from .printer import to_wgsl
from .scope import is_entry, resolve
from .types import canon, concretize, infer, lit_type, register_structs
from .wgsl import parse


@dataclass
class Options:
    dce: bool = True
    inline: bool = True
    inline_lets: bool = True
    splat: bool = True
    rewrite: bool = True
    untype: bool = True
    literals: bool = True
    aliases: bool = True
    rename: bool = True
    type_aliases: bool = True
    keep: set = field(default_factory=set)      # extra names never renamed or dropped


_IMPURE_BUILTINS = re.compile(
    r"^(atomic\w+|textureStore|textureBarrier|storageBarrier|workgroupBarrier|"
    r"workgroupUniformLoad|rayQuery\w+)$")


def is_pure(e) -> bool:
    for n in walk(e):
        if isinstance(n, Call):
            c = n.callee
            if c.sym is not None and c.sym.kind == "fn":
                return False
            if c.sym is None and _IMPURE_BUILTINS.match(c.name):
                return False
    return True


# ---------------------------------------------------------------------------- literals

def _digits(v: float, kind: str):
    """Shortest round-trip decimal digits and exponent: v = 0.DIGITS * 10**exp."""
    if kind == "f":
        s = np.format_float_scientific(np.float32(v), unique=True, trim="-")
    elif kind == "h":
        s = np.format_float_scientific(np.float16(v), unique=True, trim="-")
    else:
        s = np.format_float_scientific(np.float64(v), unique=True, trim="-")
    mant, _, ex = s.partition("e")
    digits = mant.replace(".", "").lstrip("0") or "0"
    exp = int(ex) + 1
    digits = digits.rstrip("0") or "0"
    return digits, exp


def _float_candidates(digits, exp):
    """Decimal spellings of 0.digits * 10**exp, without suffix."""
    out = []
    n = len(digits)
    if digits == "0":
        return ["0."]
    # positional
    if exp >= n:
        out.append(digits + "0" * (exp - n) + ".")
    elif exp > 0:
        out.append(digits[:exp] + "." + digits[exp:])
    else:
        out.append("." + "0" * (-exp) + digits)
    # scientific with integer mantissa: digits * 10**(exp-n)
    e = exp - n
    if e:
        out.append(f"{digits}e{e}")
    # scientific with one leading digit and a fraction
    if n > 1:
        e2 = exp - 1
        out.append(f"{digits[0]}.{digits[1:]}e{e2}" if e2 else f"{digits[0]}.{digits[1:]}")
    return out


def _parse_float(text: str) -> float:
    t = text.rstrip("fh")
    if t.lower().startswith("0x"):
        if "p" not in t.lower():
            t += "p0"
        return float.fromhex(t)
    return float(t)


def shorten_literal(text: str) -> str:
    if text in ("true", "false"):
        return text
    ty = lit_type(text)
    is_hex = text.lower().startswith("0x")
    if ty in ("AInt", "i32", "u32", "i64", "u64"):
        suffix = {"AInt": "", "i32": "i", "u32": "u", "i64": "li", "u64": "lu"}[ty]
        body = text[:len(text) - len(suffix)] if suffix else text
        v = int(body, 16) if is_hex else int(body)
        dec, hx = f"{v}{suffix}", f"0x{v:x}{suffix}"
        return dec if len(dec) <= len(hx) else hx
    kind = {"AFloat": "", "f32": "f", "f16": "h"}[ty]
    try:
        v = _parse_float(text)
    except (ValueError, OverflowError):
        return text
    if not math.isfinite(v):
        return text
    ref = _round(v, kind)
    digits, exp = _digits(ref, kind)
    best = text
    for c in _float_candidates(digits, exp):
        cand = c + kind
        if kind and c.endswith(".") and c != "0.":
            cand = c[:-1] + kind          # '2f' is a valid f32 literal; '0f' too
        elif kind and c == "0.":
            cand = "0" + kind
        if lit_type(cand) != ty:
            continue
        if _round(_parse_float(cand), kind) != ref:
            continue
        if len(cand) < len(best):
            best = cand
    return best


def _round(v, kind):
    if kind == "f":
        return float(np.float32(v))
    if kind == "h":
        return float(np.float16(v))
    return v


# ---------------------------------------------------------------------------- passes

def _entry_fns(m: Module):
    return [d for d in m.decls if isinstance(d, Fn) and is_entry(d)]


def pass_drop_asserts(m: Module):
    m.decls = [d for d in m.decls if not isinstance(d, ConstAssert)]
    for n in walk(m):
        if isinstance(n, Block):
            n.stmts = [s for s in n.stmts if not isinstance(s, ConstAssert)]


def pass_dce_module(m: Module, opts: Options):
    entries = _entry_fns(m)
    if not entries:
        return
    r = resolve(m)
    roots = set()
    for d in m.decls:
        s = getattr(d, "sym", None)
        if s is None:
            continue
        if (isinstance(d, Fn) and is_entry(d)) or (isinstance(d, Decl) and d.kind == "override") \
                or d.name in opts.keep:
            roots.add(s)
    live, stack = set(), list(roots)
    while stack:
        s = stack.pop()
        if s in live:
            continue
        live.add(s)
        stack.extend(r.uses.get(s, ()))
    m.decls = [d for d in m.decls if getattr(d, "sym", None) is None or d.sym in live]


def pass_dce_locals(m: Module):
    for _ in range(10):
        resolve(m)
        changed = False
        for blk in [n for n in walk(m) if isinstance(n, Block)]:
            keep = []
            for s in blk.stmts:
                if isinstance(s, Decl) and s.sym is not None and not s.sym.refs and (
                        s.init is None or is_pure(s.init)):
                    changed = True
                    continue
                keep.append(s)
            blk.stmts = keep
        if not changed:
            return


_SUFFIX_FOR = {"f32": "f", "i32": "i", "u32": "u", "f16": "h"}


def _typed_literal(lit: Lit, ty: str | None) -> Lit | None:
    """The literal re-spelled so it carries type ``ty`` on its own, or None."""
    lt = lit_type(lit.text)
    if ty is None:
        return lit
    if lt == ty:
        return lit
    if ty not in _SUFFIX_FOR or lt not in ("AInt", "AFloat"):
        return None
    suf = _SUFFIX_FOR[ty]
    if ty in ("i32", "u32"):
        if lt != "AInt":
            return None
        return Lit(lit.text + suf)
    v = _parse_float(lit.text) if lt == "AFloat" else float(int(lit.text, 0))
    if _round(v, suf) != v:
        return None
    return Lit(shorten_literal(repr(v) + suf))


def pass_inline_consts(m: Module):
    r = resolve(m)
    for d in list(m.decls):
        if not (isinstance(d, Decl) and d.kind == "const" and d.init is not None):
            continue
        init = d.init
        neg = False
        if isinstance(init, Unary) and init.op == "-" and isinstance(init.expr, Lit):
            neg, init = True, init.expr
        if not isinstance(init, Lit) or init.text in ("true", "false"):
            continue
        ty = canon(d.type) if d.type is not None else None
        lit = _typed_literal(init, ty)
        if lit is None:
            continue
        lit_text = shorten_literal(lit.text)
        L = len(lit_text) + (1 if neg else 0)
        n = len(d.sym.refs)
        # the declaration's cost once its name is one character, against L-1 extra per use
        decl_cost = len(to_wgsl(Module([], [d]))) - (len(d.name) - 1)
        if n * (L - 1) >= decl_cost:
            continue
        for ref in d.sym.refs:
            repl = Lit(lit_text) if not neg else Unary("-", Lit(lit_text))
            _replace_node(m, ref, repl)
        m.decls.remove(d)


def _replace_node(root, old, new):
    """Replace node ``old`` (by identity) everywhere under root."""
    for n in walk(root):
        for f in n._fields:
            v = getattr(n, f)
            if v is old:
                setattr(n, f, new)
                return True
            if isinstance(v, list):
                for k, x in enumerate(v):
                    if x is old:
                        v[k] = new
                        return True
    raise KeyError("node not found")


def _lvalue_pure(e) -> bool:
    if isinstance(e, Ident):
        return True
    if isinstance(e, Member):
        return _lvalue_pure(e.expr)
    if isinstance(e, Index):
        return _lvalue_pure(e.expr) and is_pure(e.index) and not any(
            isinstance(x, Call) for x in walk(e.index))
    if isinstance(e, Unary) and e.op == "*":
        return _lvalue_pure(e.expr)
    return False


_COMPOUND = {"+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>"}


def pass_rewrite(m: Module):
    resolve(m)
    register_structs(m)
    for n in list(walk(m)):
        if isinstance(n, Block):
            out = []
            for s in n.stmts:
                if isinstance(s, Empty):
                    continue
                if isinstance(s, Assign) and s.op == "=" and isinstance(s.rhs, Binary) \
                        and s.rhs.op in _COMPOUND and not s.rhs.paren and _lvalue_pure(s.lhs) \
                        and s.rhs.left == s.lhs:
                    s = Assign(s.lhs, s.rhs.op + "=", s.rhs.right)
                if isinstance(s, Assign) and s.op in ("+=", "-=") and isinstance(s.rhs, Lit) \
                        and lit_type(s.rhs.text) in ("AInt", "i32", "u32") \
                        and int(s.rhs.text.rstrip("iu"), 0) == 1 \
                        and infer(s.lhs) in ("i32", "u32"):
                    s = IncDec(s.lhs, "++" if s.op == "+=" else "--")
                if isinstance(s, If) and isinstance(s.els, Block) and not s.els.stmts \
                        and not s.els.attrs:
                    s.els = None
                out.append(s)
            n.stmts = out
        if isinstance(n, For):
            for attr in ("init", "update"):
                s = getattr(n, attr)
                if isinstance(s, Assign) and s.op == "=" and isinstance(s.rhs, Binary) \
                        and s.rhs.op in _COMPOUND and not s.rhs.paren and _lvalue_pure(s.lhs) \
                        and s.rhs.left == s.lhs:
                    s = Assign(s.lhs, s.rhs.op + "=", s.rhs.right)
                    setattr(n, attr, s)
                if isinstance(s, Assign) and s.op in ("+=", "-=") and isinstance(s.rhs, Lit) \
                        and lit_type(s.rhs.text) in ("AInt", "i32", "u32") \
                        and int(s.rhs.text.rstrip("iu"), 0) == 1 and infer(s.lhs) in ("i32", "u32"):
                    setattr(n, attr, IncDec(s.lhs, "++" if s.op == "+=" else "--"))
    for d in m.decls:
        if isinstance(d, Fn) and d.ret is None and d.body.stmts and \
                isinstance(d.body.stmts[-1], Return) and d.body.stmts[-1].expr is None:
            d.body.stmts.pop()


def pass_untype(m: Module):
    resolve(m)
    register_structs(m)
    for n in walk(m):
        if isinstance(n, Decl) and n.kind in ("let", "var") and n.type is not None \
                and n.init is not None:
            if n.kind == "var" and n.tmpl and not (
                    len(n.tmpl) == 1 and isinstance(n.tmpl[0], Ident)
                    and n.tmpl[0].name in ("private", "function")):
                continue
            want = canon(n.type)
            got = concretize(infer(n.init))
            if want is not None and got == want:
                n.type = None
                if n.sym is not None:
                    n.sym.type_cache = None


_SPLAT = {f"vec{n}{s}": n for n in (2, 3, 4) for s in "fiuh"} | {f"vec{n}": n for n in (2, 3, 4)}


def pass_splat(m: Module):
    """vec3f(x, x, x) -> vec3f(x) when every argument is the same literal or name."""
    resolve(m)
    for n in walk(m):
        if isinstance(n, Call) and n.callee.sym is None and len(n.args) >= 2:
            size = _SPLAT.get(n.callee.name)
            if size is None and n.callee.name in ("vec2", "vec3", "vec4") and n.callee.tmpl:
                size = int(n.callee.name[3])
            if size != len(n.args):
                continue
            a0 = n.args[0]
            if not isinstance(a0, (Lit, Ident)) or (isinstance(a0, Ident) and a0.tmpl):
                continue
            if isinstance(a0, Ident):
                t = infer(a0)
                if t is None or not (t in ("f32", "i32", "u32", "f16", "bool", "AInt", "AFloat")):
                    continue
            if all(x == a0 for x in n.args[1:]):
                n.args = [a0]


_MOVABLE_BAN = re.compile(r"^(dpdx\w*|dpdy\w*|fwidth\w*|textureSample\w*|subgroup\w*|quad\w*)$")


def _calls_ok_to_move(e) -> bool:
    for n in walk(e):
        if isinstance(n, Call) and n.callee.sym is None and _MOVABLE_BAN.match(n.callee.name):
            return False
    return is_pure(e)


def _reads_mutable(e) -> bool:
    for n in walk(e):
        if isinstance(n, Unary) and n.op == "*":
            return True
        if isinstance(n, Ident) and n.sym is not None:
            k = n.sym.kind
            if k == "var":
                return True
            if k in ("param", "let"):
                node = n.sym.node
                ty = canon(node.type) if node.type is not None else infer(node.init) if getattr(node, "init", None) is not None else None
                if ty is None or ty.startswith("ptr"):
                    return True
    return False


def _has_effects(stmt) -> bool:
    for n in walk(stmt):
        if isinstance(n, (Assign, IncDec)):
            return True
        if isinstance(n, Call) and not is_pure(n):
            return True
    return False


def _path(root, target):
    if root is target:
        return [root]
    from .ast import children
    for c in children(root):
        p = _path(c, target)
        if p:
            return [root] + p
    return None


_SIMPLE = (Decl, Assign, IncDec, Return)


def pass_inline_lets(m: Module):
    """Inline a function-scope let that is used once, when moving its initialiser cannot
    change what it evaluates to: the initialiser is pure, has a concrete type, does not
    move into a loop, and nothing it reads is written between the let and the use."""
    from .ast import ExprStmt
    for _ in range(20):
        resolve(m)
        register_structs(m)
        changed = False
        for blk in [n for n in walk(m) if isinstance(n, Block)]:
            for i, st in enumerate(blk.stmts):
                if not (isinstance(st, Decl) and st.kind == "let" and st.sym is not None
                        and len(st.sym.refs) == 1 and st.init is not None):
                    continue
                e = st.init
                if not _calls_ok_to_move(e):
                    continue
                ty = infer(e)
                if ty is None or concretize(ty) != ty:
                    continue
                if st.type is not None and canon(st.type) != ty:
                    continue
                use = st.sym.refs[0]
                j = next((k for k in range(i + 1, len(blk.stmts))
                          if _path(blk.stmts[k], use) is not None), None)
                if j is None:
                    continue
                target = blk.stmts[j]
                path = _path(target, use)
                if isinstance(target, (_SIMPLE, ExprStmt)):
                    pass
                elif isinstance(target, If) and len(path) > 1 and path[1] is target.cond:
                    pass
                elif isinstance(target, Switch) and len(path) > 1 and path[1] is target.expr:
                    pass
                else:
                    continue
                if _reads_mutable(e):
                    if any(_has_effects(x) for x in blk.stmts[i + 1:j]):
                        continue
                    if any(isinstance(n, Call) and not is_pure(n) for n in walk(target)):
                        continue
                _replace_node(target, use, e)
                del blk.stmts[i]
                changed = True
                break
            if changed:
                break
        if not changed:
            return


def pass_literals(m: Module):
    for n in walk(m):
        if isinstance(n, Lit):
            n.text = shorten_literal(n.text)


_ALIAS_OF = {}
for _n in (2, 3, 4):
    for _s, _t in (("i", "i32"), ("u", "u32"), ("f", "f32"), ("h", "f16")):
        _ALIAS_OF[(f"vec{_n}", _t)] = f"vec{_n}{_s}"
for _c in (2, 3, 4):
    for _r in (2, 3, 4):
        for _s, _t in (("f", "f32"), ("h", "f16")):
            _ALIAS_OF[(f"mat{_c}x{_r}", _t)] = f"mat{_c}x{_r}{_s}"


def pass_aliases(m: Module):
    resolve(m)
    user = {d.name for d in m.decls if hasattr(d, "name")}
    for n in walk(m):
        if isinstance(n, Ident) and n.tmpl and len(n.tmpl) == 1 and isinstance(n.tmpl[0], Ident) \
                and n.tmpl[0].sym is None and not n.tmpl[0].tmpl and n.sym is None:
            a = _ALIAS_OF.get((n.name, n.tmpl[0].name))
            if a and a not in user:
                n.name, n.tmpl = a, None


def pass_type_aliases(m: Module):
    """Declare ``alias a = vec4f;`` for predeclared types used often enough that the
    alias pays for itself (before renaming, which then gives it a one-letter name)."""
    from .ast import Alias
    from .names import TYPES
    # only names that are complete types on their own (not vec3, array, mat2x2, texture_2d)
    concrete = {t for t in TYPES if t in ("bool", "f16", "f32", "i32", "u32", "sampler",
                "sampler_comparison", "texture_external") or re.fullmatch(r"vec[234][iufh]", t)
                or re.fullmatch(r"mat[234]x[234][fh]", t) or (t.startswith("texture_depth")
                and "multisampled" not in t)}
    resolve(m)
    user = {getattr(d, "name", None) for d in m.decls}
    # naga types array<alias, N> as distinct from array<T, N>: leave template arguments alone
    in_tmpl = {id(a) for n in walk(m) if isinstance(n, Ident) and n.tmpl for a in n.tmpl}
    uses: dict[str, list] = {}
    for n in walk(m):
        if isinstance(n, Ident) and n.sym is None and not n.tmpl and n.name in concrete \
                and n.name not in user and id(n) not in in_tmpl:
            uses.setdefault(n.name, []).append(n)
    added = []
    for name, refs in sorted(uses.items()):
        # one-letter alias name after renaming: saves len(name)-1 per use, costs 'alias a=NAME;'
        if len(refs) * (len(name) - 1) <= len(name) + 9:
            continue
        alias_name = f"__alias_{name}"
        added.append(Alias([], alias_name, Ident(name, None)))
        for r in refs:
            r.name = alias_name
    m.decls[:0] = added


def pass_rename(m: Module, opts: Options):
    r = resolve(m)
    used_unresolved = {n.name for n in walk(m) if isinstance(n, Ident) and n.sym is None}
    keep_syms = set()
    for s in r.symbols:
        if s.is_module and ((s.kind == "fn" and is_entry(s.node)) or s.kind == "override"
                            or s.name in opts.keep):
            keep_syms.add(s)
    taken = used_unresolved | {s.name for s in keep_syms} | FORBIDDEN | opts.keep

    def weight(s):
        return len(s.refs) + 1

    mod_syms = sorted((s for s in r.symbols if s.is_module and s not in keep_syms),
                      key=lambda s: (-weight(s), s.name))
    gen = name_stream()
    mod_names = []
    for s in mod_syms:
        name = next(gen)
        while name in taken:
            name = next(gen)
        s.new_name = name
        mod_names.append(name)
    final_module = {s: (s.new_name or s.name) for s in r.symbols if s.is_module}

    # function-scope symbols: per function, avoid every module name the function sees
    by_fn: dict = {}
    for s in r.symbols:
        if not s.is_module:
            by_fn.setdefault(id(s.fn), (s.fn, []))[1].append(s)
    for fn, syms in by_fn.values():
        seen = set()
        for n in walk(fn):
            if isinstance(n, Ident) and n.sym is not None and n.sym.is_module:
                seen.add(final_module[n.sym])
        avoid = taken | seen | {final_module[fn.sym]}
        g = name_stream()
        for s in sorted(syms, key=lambda s: (-weight(s), s.name)):
            name = next(g)
            while name in avoid:
                name = next(g)
            s.new_name = name
            avoid = avoid | {name}

    for s in r.symbols:
        if s.new_name and s.new_name != s.name:
            s.node.name = s.new_name
            for ref in s.refs:
                ref.name = s.new_name

    # struct members: one global mapping, so `a.foo` renames without knowing a's type
    counts = Counter()
    for d in m.decls:
        if isinstance(d, Struct):
            for mb in d.members:
                counts[mb.name] += 1
    for n in walk(m):
        if isinstance(n, Member) and n.name in counts:
            counts[n.name] += 1
    fixed = {k for k in counts if is_swizzle(k) or k in BUILTIN_MEMBERS or k in opts.keep}
    mapping = {}
    g = name_stream()
    member_taken = set(fixed) | {"x", "y", "z", "w", "r", "g", "b", "a"}
    for k, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if k in fixed:
            continue
        name = next(g)
        while name in member_taken or is_swizzle(name) or name in BUILTIN_MEMBERS:
            name = next(g)
        mapping[k] = name
        member_taken.add(name)
    for d in m.decls:
        if isinstance(d, Struct):
            for mb in d.members:
                mb.name = mapping.get(mb.name, mb.name)
    for n in walk(m):
        if isinstance(n, Member) and n.name in mapping:
            n.name = mapping[n.name]
    return {s.name: s.new_name for s in r.symbols if s.new_name} | {
        "members": mapping}


def minify_module(m: Module, opts: Options | None = None) -> Module:
    opts = opts or Options()
    m = copy.deepcopy(m)
    pass_drop_asserts(m)
    if opts.dce:
        pass_dce_module(m, opts)
        pass_dce_locals(m)
    if opts.inline:
        pass_inline_consts(m)
        if opts.dce:
            pass_dce_module(m, opts)
    if opts.rewrite:
        pass_rewrite(m)
    if opts.inline_lets:
        pass_inline_lets(m)
    if opts.splat:
        pass_splat(m)
    if opts.untype:
        pass_untype(m)
    if opts.literals:
        pass_literals(m)
    if opts.aliases:
        pass_aliases(m)
    if opts.rename and opts.type_aliases:
        pass_type_aliases(m)
    if opts.rename:
        pass_rename(m, opts)
    return m


def minify(src: str, opts: Options | None = None) -> str:
    return to_wgsl(minify_module(parse(src), opts))
