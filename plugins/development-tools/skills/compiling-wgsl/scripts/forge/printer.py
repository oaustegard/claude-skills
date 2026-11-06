"""Print a WGSL AST, either compact (the fewest characters that re-parse to the same
tree) or pretty (indented, one statement per line).

Parentheses come from WGSL's grammar, not from a C precedence table. WGSL refuses to
mix some operators without them (``a & b | c``, ``a << b + c``, ``-a.x`` versus
``(-a).x``), so each operand slot accepts a fixed set of expression classes and
anything else is wrapped.

A compact print can create a template list that was not in the source: ``f((a<b), c>d)``
printed as ``f(a<b,c>d)`` re-lexes as ``a<b,c>`` followed by ``d``. After printing, the
output is re-lexed and any relational ``<``/``>`` the lexer took for a template delimiter
gets its expression parenthesised, and the module is printed again.
"""
from __future__ import annotations

from .ast import (
    Alias, Assign, Binary, Block, Break, BreakIf, Call, ConstAssert, Continue, Decl,
    Directive, Discard, Empty, ExprStmt, For, Fn, Ident, If, IncDec, Index, Lit, Loop, Member,
    Module, Return, Struct, Switch, Unary, While,
)
from .wgsl import lex

_CLASS = {"*": "mul", "/": "mul", "%": "mul", "+": "add", "-": "add", "<<": "shift",
          ">>": "shift", "<": "rel", ">": "rel", "<=": "rel", ">=": "rel", "==": "rel",
          "!=": "rel", "&": "and", "|": "or", "^": "xor", "&&": "land", "||": "lor"}

_U = {"primary", "unary"}
_REL_OPERAND = _U | {"mul", "add", "shift"}
# (left-operand classes, right-operand classes) for each binary class
_SLOTS = {
    "mul": (_U | {"mul"}, _U),
    "add": (_U | {"mul", "add"}, _U | {"mul"}),
    "shift": (_U, _U),
    "rel": (_REL_OPERAND, _REL_OPERAND),
    "and": (_U | {"and"}, _U),
    "or": (_U | {"or"}, _U),
    "xor": (_U | {"xor"}, _U),
    "land": (_REL_OPERAND | {"rel", "land"}, _REL_OPERAND | {"rel"}),
    "lor": (_REL_OPERAND | {"rel", "lor"}, _REL_OPERAND | {"rel"}),
}

# pairs of adjacent characters that would lex as a different token if not separated
_GLUE = {("-", "-"), ("+", "+"), ("&", "&"), ("|", "|"), ("<", "<"), (">", ">"), ("<", "="),
         (">", "="), ("=", "="), ("!", "="), ("+", "="), ("-", "="), ("*", "="), ("/", "="),
         ("%", "="), ("&", "="), ("|", "="), ("^", "="), ("/", "/"), ("/", "*"), ("*", "/"),
         ("-", ">")}


def _wordish(c):
    return c.isalnum() or c == "_" or ord(c) > 127


def expr_class(e) -> str:
    if isinstance(e, Binary):
        return "primary" if e.paren else _CLASS[e.op]
    if isinstance(e, Unary):
        return "unary"
    return "primary"


class _Out:
    """Token sink. Each token carries a role so the template check can find it later.
    In pretty mode, ``pre``/``post`` ask for a space before/after the token."""

    def __init__(self, pretty):
        self.pretty = pretty
        self.parts: list[str] = []
        self.last = ""
        self.last_role = None
        self.last_is_number = False
        self.post = False
        self.pos = 0
        self.marks: list[tuple[int, str, object]] = []   # (offset, role, node)
        self.indent = 0
        self.at_line_start = True

    def tok(self, text, role=None, node=None, pre=False, post=False):
        if self.pretty and self.at_line_start:
            self._raw("    " * self.indent)
            self.at_line_start = False
            self.last = ""
            self.post = False
        a, b = self.last[-1:], text[0]
        need = False
        if a and _wordish(b) and (_wordish(a) or (a == "." and self.last_is_number)):
            need = True          # 'x' 'y' would merge; '1.' 'f' would lex as '1.f'
        elif (a, b) in _GLUE:
            need = True
        elif self.last_role == "tend" and b == "=":
            need = True
        elif self.pretty and a and (pre or self.post) and text not in (",", ";", ")", "]"):
            need = True
        if need:
            self._raw(" ")
        if role:
            self.marks.append((self.pos, role, node))
        self._raw(text)
        self.last = text
        self.last_role = role
        self.last_is_number = text[0].isdigit() or (text[0] == "." and len(text) > 1)
        self.post = post

    def _raw(self, s):
        self.parts.append(s)
        self.pos += len(s)

    def newline(self):
        if self.pretty:
            self._raw("\n")
            self.at_line_start = True
            self.last = ""

    def text(self):
        return "".join(self.parts)


_KW_POST = {"fn", "struct", "var", "let", "const", "override", "alias", "return", "if", "else",
            "switch", "case", "loop", "for", "while", "continuing", "enable", "requires",
            "const_assert"}


class Printer:
    def __init__(self, pretty=False):
        self.pretty = pretty

    def print(self, module: Module) -> str:
        for _ in range(8):
            self.o = _Out(self.pretty)
            self.module(module)
            out = self.o.text()
            bad = self._template_conflicts(out)
            if not bad:
                return out
            for node in bad:
                node.paren = True
        raise RuntimeError("could not print without template-list ambiguity")

    def _template_conflicts(self, out):
        lexed = {t.pos: t.tmpl for t in lex(out) if t.text in ("<", ">")}
        bad = []
        for pos, role, node in self.o.marks:
            got = lexed.get(pos)
            if role == "relop" and got is not None:
                bad.append(node)
            elif role in ("tstart", "tend") and got != role[1:]:
                raise RuntimeError(f"template delimiter at {pos} re-lexed as {got!r}")
        return bad

    # -- helpers
    def t(self, text, role=None, node=None, pre=False, post=False):
        if text in _KW_POST or text in (",", ":"):
            post = True
        if text in ("{", "=", "->") or (role is None and text in _CLASS and node is not None):
            pre = post = True
        self.o.tok(text, role, node, pre, post)

    def sep_list(self, items, fn, sep=","):
        for k, x in enumerate(items):
            if k:
                self.t(sep)
            fn(x)

    def attrs(self, attrs):
        for a in attrs:
            self.t("@")
            self.t(a.name)
            if a.args is not None:
                self.t("(")
                self.sep_list(a.args, self.expr)
                self.t(")")
            self.o.post = True

    def tmpl(self, args):
        self.t("<", "tstart")
        self.sep_list(args, self.expr)
        self.t(">", "tend")

    # -- module
    def module(self, m: Module):
        for d in m.directives:
            self.directive(d)
        for k, d in enumerate(m.decls):
            if self.pretty and k:
                self.o.newline()
            self.decl_global(d)

    def directive(self, d: Directive):
        self.t(d.kind)
        # body is pre-normalised text: names, commas, dots and parens
        import re
        for piece in re.findall(r"[A-Za-z0-9_]+|[^A-Za-z0-9_\s]", d.body):
            self.t(piece)
        self.t(";")
        self.o.newline()

    def decl_global(self, d):
        if isinstance(d, Struct):
            self.attrs(d.attrs)
            self.t("struct")
            self.t(d.name)
            self.t("{")
            self.o.indent += 1
            self.o.newline()
            for k, mbr in enumerate(d.members):
                if k:
                    self.t(",")
                    self.o.newline()
                self.attrs(mbr.attrs)
                self.t(mbr.name)
                self.t(":")
                self.type(mbr.type)
            if self.pretty and d.members:
                self.t(",")
            self.o.indent -= 1
            self.o.newline()
            self.t("}")
            self.o.newline()
        elif isinstance(d, Fn):
            self.attrs(d.attrs)
            self.t("fn")
            self.t(d.name)
            self.t("(")
            for k, p in enumerate(d.params):
                if k:
                    self.t(",")
                self.attrs(p.attrs)
                self.t(p.name)
                self.t(":")
                self.type(p.type)
            self.t(")")
            if d.ret is not None:
                self.t("->")
                self.attrs(d.ret_attrs)
                self.type(d.ret)
            self.block(d.body)
            self.o.newline()
        elif isinstance(d, Decl):
            self.decl(d)
            self.t(";")
            self.o.newline()
        elif isinstance(d, Alias):
            self.attrs(d.attrs)
            self.t("alias")
            self.t(d.name)
            self.t("=")
            self.type(d.type)
            self.t(";")
            self.o.newline()
        elif isinstance(d, ConstAssert):
            self.t("const_assert")
            self.expr(d.expr)
            self.t(";")
            self.o.newline()
        else:
            raise TypeError(d)

    def decl(self, d: Decl):
        self.attrs(d.attrs)
        self.t(d.kind)
        if d.tmpl:
            self.tmpl(d.tmpl)
        self.t(d.name)
        if d.type is not None:
            self.t(":")
            self.type(d.type)
        if d.init is not None:
            self.t("=")
            self.expr(d.init)

    def type(self, ty: Ident):
        self.t(ty.name)
        if ty.tmpl:
            self.tmpl(ty.tmpl)

    # -- statements
    def block(self, b: Block, inline_attrs=True):
        if inline_attrs:
            self.attrs(b.attrs)
        self.t("{")
        self.o.indent += 1
        self.o.newline()
        for s in b.stmts:
            self.stmt(s)
        self.o.indent -= 1
        if self.pretty and not self.o.at_line_start:
            self.o.newline()
        self.t("}")

    def stmt(self, s):
        o = self.o
        if isinstance(s, Block):
            self.block(s)
            o.newline()
        elif isinstance(s, Return):
            self.t("return")
            if s.expr is not None:
                self.expr(s.expr)
            self.t(";")
            o.newline()
        elif isinstance(s, If):
            self.if_stmt(s)
            o.newline()
        elif isinstance(s, Switch):
            self.attrs(s.attrs)
            self.t("switch")
            self.expr(s.expr)
            self.attrs(s.body_attrs)
            self.t("{")
            o.indent += 1
            o.newline()
            for c in s.cases:
                self.attrs(c.attrs)
                if c.selectors == [None]:
                    self.t("default")
                else:
                    self.t("case")
                    for k, sel in enumerate(c.selectors):
                        if k:
                            self.t(",")
                        if sel is None:
                            self.t("default")
                        else:
                            self.expr(sel)
                self.block(c.body)
                o.newline()
            o.indent -= 1
            self.t("}")
            o.newline()
        elif isinstance(s, Loop):
            self.attrs(s.attrs)
            self.t("loop")
            self.attrs(s.body_attrs)
            self.t("{")
            o.indent += 1
            o.newline()
            for x in s.stmts:
                self.stmt(x)
            if s.continuing is not None or s.break_if is not None:
                self.t("continuing")
                self.attrs(s.cont_attrs)
                self.t("{")
                o.indent += 1
                o.newline()
                for x in s.continuing or []:
                    self.stmt(x)
                if s.break_if is not None:
                    self.t("break")
                    self.t("if")
                    self.expr(s.break_if)
                    self.t(";")
                    o.newline()
                o.indent -= 1
                self.t("}")
                o.newline()
            o.indent -= 1
            self.t("}")
            o.newline()
        elif isinstance(s, For):
            self.attrs(s.attrs)
            self.t("for")
            self.t("(")
            if s.init is not None:
                self.simple(s.init)
            self.t(";")
            if s.cond is not None:
                self.expr(s.cond)
            self.t(";")
            if s.update is not None:
                self.simple(s.update)
            self.t(")")
            self.block(s.body)
            o.newline()
        elif isinstance(s, While):
            self.attrs(s.attrs)
            self.t("while")
            self.expr(s.cond)
            self.block(s.body)
            o.newline()
        elif isinstance(s, Break):
            self.t("break")
            self.t(";")
            o.newline()
        elif isinstance(s, BreakIf):
            self.t("break")
            self.t("if")
            self.expr(s.cond)
            self.t(";")
            o.newline()
        elif isinstance(s, Continue):
            self.t("continue")
            self.t(";")
            o.newline()
        elif isinstance(s, Discard):
            self.t("discard")
            self.t(";")
            o.newline()
        elif isinstance(s, ConstAssert):
            self.t("const_assert")
            self.expr(s.expr)
            self.t(";")
            o.newline()
        elif isinstance(s, Empty):
            pass
        else:
            self.simple(s)
            self.t(";")
            o.newline()

    def simple(self, s):
        if isinstance(s, Decl):
            self.decl(s)
        elif isinstance(s, Assign):
            self.expr(s.lhs)
            self.t(s.op, pre=True, post=True)
            self.expr(s.rhs)
        elif isinstance(s, IncDec):
            self.expr(s.lhs)
            self.t(s.op)
        elif isinstance(s, ExprStmt):
            self.expr(s.expr)
        else:
            raise TypeError(s)

    def if_stmt(self, s: If):
        self.attrs(s.attrs)
        self.t("if")
        self.expr(s.cond)
        self.block(s.then)
        if s.els is not None:
            self.t("else")
            if isinstance(s.els, If):
                self.if_stmt(s.els)
            else:
                self.block(s.els)

    # -- expressions
    def expr(self, e, allowed=None):
        cls = expr_class(e)
        wrap = allowed is not None and cls not in allowed
        if wrap:
            self.t("(")
        if isinstance(e, Binary):
            if e.paren and not wrap:
                self.t("(")
            left, right = _SLOTS[_CLASS[e.op]]
            self.expr(e.left, left)
            role = "relop" if e.op in ("<", ">", "<=", ">=") else None
            self.t(e.op, role, e, pre=True, post=True)
            self.expr(e.right, right)
            if e.paren and not wrap:
                self.t(")")
        elif isinstance(e, Unary):
            self.t(e.op)
            self.expr(e.expr, _U)
        elif isinstance(e, Lit):
            self.t(e.text)
        elif isinstance(e, Ident):
            self.type(e)
        elif isinstance(e, Call):
            self.type(e.callee)
            self.t("(")
            self.sep_list(e.args, self.expr)
            self.t(")")
        elif isinstance(e, Member):
            self.expr(e.expr, {"primary"})
            self.t(".")
            self.t(e.name)
        elif isinstance(e, Index):
            self.expr(e.expr, {"primary"})
            self.t("[")
            self.expr(e.index)
            self.t("]")
        else:
            raise TypeError(e)
        if wrap:
            self.t(")")


def to_wgsl(module: Module, pretty=False) -> str:
    return Printer(pretty).print(module)
