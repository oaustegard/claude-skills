"""Bind every identifier reference to the declaration it names.

After ``resolve(module)`` each declaration node has ``.sym`` (a Symbol) and every Ident
that names a user declaration has ``.sym`` pointing at the same Symbol, with the Ident
appended to ``Symbol.refs``. Identifiers that resolve to nothing are predeclared
(builtins, types) or context-dependent enumerants, and keep ``sym = None``.

Scoping follows WGSL: module-scope declarations are visible everywhere regardless of
order; a function-scope name is visible from the end of its declaration to the end of
its block; a for-loop header opens a scope around its body; a loop's continuing block
sees the loop body's declarations.
"""
from __future__ import annotations

from .ast import (
    Alias, Assign, Block, BreakIf, Call, ConstAssert, Decl, ExprStmt, For, Fn, Ident, If, IncDec,
    Index, Lit, Loop, Member, Module, Return, Struct, Switch, Unary, Binary, While,
)

# attributes whose arguments are context-dependent names, never references
_NAME_ATTRS = {"builtin", "interpolate", "diagnostic"}


class Symbol:
    __slots__ = ("kind", "name", "node", "fn", "refs", "new_name", "type_cache")

    def __init__(self, kind, name, node, fn=None):
        self.kind = kind          # fn struct alias const override var let param
        self.name = name
        self.node = node
        self.fn = fn              # owning Fn for function-scope symbols, else None
        self.refs: list[Ident] = []
        self.new_name = None
        self.type_cache = None

    @property
    def is_module(self):
        return self.fn is None

    def __repr__(self):
        return f"Symbol({self.kind} {self.name})"


def decl_kind(d):
    if isinstance(d, Fn):
        return "fn"
    if isinstance(d, Struct):
        return "struct"
    if isinstance(d, Alias):
        return "alias"
    if isinstance(d, Decl):
        return d.kind
    return None


def is_entry(fn: Fn) -> bool:
    return any(a.name in ("vertex", "fragment", "compute") for a in fn.attrs)


class Resolver:
    def __init__(self, module: Module):
        self.module = module
        self.globals: dict[str, Symbol] = {}
        self.scopes: list[dict[str, Symbol]] = []
        self.fn = None
        self.symbols: list[Symbol] = []
        self.current_owner = None     # module-level Symbol whose body is being walked
        self.uses: dict[Symbol, set] = {}   # module symbol -> module symbols it references

    def run(self):
        for d in self.module.decls:
            k = decl_kind(d)
            if k:
                s = Symbol(k, d.name, d)
                d.sym = s
                self.globals[d.name] = s
                self.symbols.append(s)
                self.uses[s] = set()
        for d in self.module.decls:
            self.current_owner = getattr(d, "sym", None)
            if isinstance(d, Fn):
                self.function(d)
            elif isinstance(d, Struct):
                for m in d.members:
                    self.attrs(m.attrs)
                    self.expr(m.type)
            elif isinstance(d, Alias):
                self.expr(d.type)
            elif isinstance(d, Decl):
                self.attrs(d.attrs)
                if d.type is not None:
                    self.expr(d.type)
                if d.init is not None:
                    self.expr(d.init)
            elif isinstance(d, ConstAssert):
                self.expr(d.expr)
        self.current_owner = None
        return self

    # -- lookup
    def lookup(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        return self.globals.get(name)

    def bind(self, ident: Ident):
        s = self.lookup(ident.name)
        ident.sym = s
        if s is not None:
            s.refs.append(ident)
            if s.is_module and self.current_owner is not None:
                self.uses[self.current_owner].add(s)

    def declare(self, kind, name, node):
        s = Symbol(kind, name, node, self.fn)
        node.sym = s
        self.scopes[-1][name] = s
        self.symbols.append(s)
        return s

    # -- walkers
    def attrs(self, attrs):
        for a in attrs:
            if a.args and a.name not in _NAME_ATTRS:
                for x in a.args:
                    self.expr(x)

    def function(self, fn: Fn):
        self.fn = fn
        self.attrs(fn.attrs)
        self.scopes = [{}]
        for p in fn.params:
            self.attrs(p.attrs)
            self.expr(p.type)
        if fn.ret is not None:
            self.attrs(fn.ret_attrs)
            self.expr(fn.ret)
        for p in fn.params:
            self.declare("param", p.name, p)
        self.block(fn.body, new_scope=False)
        self.scopes = []
        self.fn = None

    def block(self, b: Block, new_scope=True):
        if new_scope:
            self.scopes.append({})
        for s in b.stmts:
            self.stmt(s)
        if new_scope:
            self.scopes.pop()

    def stmt(self, s):
        if isinstance(s, Block):
            self.block(s)
        elif isinstance(s, Decl):
            if s.type is not None:
                self.expr(s.type)
            if s.init is not None:
                self.expr(s.init)
            self.declare(s.kind, s.name, s)
        elif isinstance(s, Return):
            if s.expr is not None:
                self.expr(s.expr)
        elif isinstance(s, If):
            self.expr(s.cond)
            self.block(s.then)
            if isinstance(s.els, If):
                self.stmt(s.els)
            elif s.els is not None:
                self.block(s.els)
        elif isinstance(s, Switch):
            self.expr(s.expr)
            for c in s.cases:
                for sel in c.selectors:
                    if sel is not None:
                        self.expr(sel)
                self.block(c.body)
        elif isinstance(s, Loop):
            self.scopes.append({})
            for x in s.stmts:
                self.stmt(x)
            for x in s.continuing or []:
                self.stmt(x)
            if s.break_if is not None:
                self.expr(s.break_if)
            self.scopes.pop()
        elif isinstance(s, For):
            self.scopes.append({})
            if s.init is not None:
                self.stmt(s.init)
            if s.cond is not None:
                self.expr(s.cond)
            if s.update is not None:
                self.stmt(s.update)
            self.block(s.body)
            self.scopes.pop()
        elif isinstance(s, While):
            self.expr(s.cond)
            self.block(s.body)
        elif isinstance(s, (BreakIf,)):
            self.expr(s.cond)
        elif isinstance(s, Assign):
            self.expr(s.lhs)
            self.expr(s.rhs)
        elif isinstance(s, IncDec):
            self.expr(s.lhs)
        elif isinstance(s, ExprStmt):
            self.expr(s.expr)
        elif isinstance(s, ConstAssert):
            self.expr(s.expr)

    def expr(self, e):
        if isinstance(e, Ident):
            if e.name != "_":
                self.bind(e)
            self.tmpl(e)
        elif isinstance(e, Call):
            self.expr(e.callee)
            for a in e.args:
                self.expr(a)
        elif isinstance(e, Binary):
            self.expr(e.left)
            self.expr(e.right)
        elif isinstance(e, Unary):
            self.expr(e.expr)
        elif isinstance(e, Member):
            self.expr(e.expr)
        elif isinstance(e, Index):
            self.expr(e.expr)
            self.expr(e.index)
        elif isinstance(e, Lit) or e is None:
            pass
        else:
            raise TypeError(e)

    def tmpl(self, e: Ident):
        if not e.tmpl:
            return
        name = e.name
        for k, a in enumerate(e.tmpl):
            # address spaces, access modes and texel formats are enumerants
            if name == "ptr" and k in (0, 2):
                continue
            if name.startswith("texture_storage"):
                continue
            self.expr(a)


def resolve(module: Module) -> Resolver:
    from .ast import walk
    for n in walk(module):
        if hasattr(n, "sym") and type(n).__name__ in ("Ident",):
            n.sym = None
    return Resolver(module).run()
