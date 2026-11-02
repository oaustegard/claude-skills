"""WGSL lexer, template-list discovery and recursive-descent parser.

The parser accepts the WGSL grammar as of the 2025 W3C Candidate Recommendation
(directives, attributes, structs, functions, module and local declarations, every
statement form) and builds the AST in ``forge.ast``. It does not type-check: a module
that parses here may still fail validation, which is what naga or Tint are for.

Template lists (``vec3<f32>``, ``array<T, N>``, ``var<storage, read>``) are found with
the spec's lexical discovery algorithm (WGSL §3.9) before parsing, so ``a < b`` and
``vec2<f32>`` are told apart the same way a conforming compiler tells them apart.
"""
from __future__ import annotations

import re

from .ast import (
    Alias, Assign, Attribute, Binary, Block, Break, BreakIf, Call, Case, ConstAssert,
    Continue, Decl, Directive, Discard, Empty, ExprStmt, For, Fn, Ident, If, IncDec, Index,
    Lit, Loop, Member, Module, Param, Return, Struct, StructMember, Switch, Unary, While,
)

KEYWORDS = {
    "alias", "break", "case", "const", "const_assert", "continue", "continuing", "default",
    "diagnostic", "discard", "else", "enable", "false", "fn", "for", "if", "let", "loop",
    "override", "requires", "return", "struct", "switch", "true", "var", "while",
}


class WGSLSyntaxError(Exception):
    def __init__(self, msg, src=None, pos=None):
        if src is not None and pos is not None:
            line = src.count("\n", 0, pos) + 1
            col = pos - (src.rfind("\n", 0, pos) + 1) + 1
            msg = f"{line}:{col}: {msg}"
        super().__init__(msg)


class Tok:
    __slots__ = ("kind", "text", "pos", "end", "tmpl")

    def __init__(self, kind, text, pos, end):
        self.kind = kind      # 'ident' | 'num' | 'op' | 'eof'
        self.text = text
        self.pos = pos
        self.end = end
        self.tmpl = None      # 'start' | 'end' for template-list delimiters

    def __repr__(self):
        t = f"/{self.tmpl}" if self.tmpl else ""
        return f"Tok({self.kind},{self.text!r}{t})"


_NUM = re.compile(
    r"""
    0[xX](?:[0-9a-fA-F]*\.[0-9a-fA-F]+|[0-9a-fA-F]+\.[0-9a-fA-F]*)(?:[pP][+-]?[0-9]+[fh]?)?
  | 0[xX][0-9a-fA-F]+[pP][+-]?[0-9]+[fh]?
  | 0[xX][0-9a-fA-F]+(?:l[iu]|[iu])?
  | (?:[0-9]*\.[0-9]+|[0-9]+\.[0-9]*)(?:[eE][+-]?[0-9]+)?[fh]?
  | [0-9]+[eE][+-]?[0-9]+[fh]?
  | 0[fh] | [1-9][0-9]*[fh]
  | 0(?:l[iu]|[iu])? | [1-9][0-9]*(?:l[iu]|[iu])?
    """,
    re.VERBOSE,
)
_IDENT = re.compile(r"[A-Za-z_\u0080-￿][A-Za-z0-9_\u0080-￿]*")
# '>' is never munched with what follows it: '>>', '>=' and '>>=' are re-formed after
# template discovery, because a template list can close with '>' right before them.
_OPS = sorted(
    ["&&", "||", "==", "!=", "<=", "<<=", "<<", "->", "++", "--", "+=", "-=", "*=", "/=",
     "%=", "&=", "|=", "^=", "@", "!", "%", "&", "(", ")", "*", "+", ",", "-", ".", "/",
     ":", ";", "<", "=", ">", "[", "]", "^", "{", "|", "}", "~"],
    key=len, reverse=True,
)
_WS = re.compile(r"[ \t\n\r\v\f\u0085‎‏  ]+")


def lex(src: str) -> list[Tok]:
    toks: list[Tok] = []
    i, n = 0, len(src)
    while i < n:
        m = _WS.match(src, i)
        if m:
            i = m.end()
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            depth, j = 1, i + 2
            while depth and j < n:
                if src.startswith("/*", j):
                    depth += 1
                    j += 2
                elif src.startswith("*/", j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            if depth:
                raise WGSLSyntaxError("unterminated block comment", src, i)
            i = j
            continue
        c = src[i]
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            m = _NUM.match(src, i)
            if not m:
                raise WGSLSyntaxError("bad number", src, i)
            toks.append(Tok("num", m.group(), i, m.end()))
            i = m.end()
            continue
        m = _IDENT.match(src, i)
        if m:
            toks.append(Tok("ident", m.group(), i, m.end()))
            i = m.end()
            continue
        for op in _OPS:
            if src.startswith(op, i):
                toks.append(Tok("op", op, i, i + len(op)))
                i += len(op)
                break
        else:
            raise WGSLSyntaxError(f"unexpected character {c!r}", src, i)
    _discover_templates(toks)
    toks = _merge_gt(toks)
    toks.append(Tok("eof", "", n, n))
    return toks


def _discover_templates(toks: list[Tok]) -> None:
    """WGSL §3.9 template list discovery, run on tokens instead of characters."""
    pending: list[tuple[int, int]] = []   # (index of '<', nesting depth)
    depth = 0
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if t.kind == "ident" and i + 1 < n and toks[i + 1].text == "<":
            pending.append((i + 1, depth))
            i += 2
            continue
        x = t.text
        if t.kind == "op":
            if x == ">":
                if pending and pending[-1][1] == depth:
                    s, _ = pending.pop()
                    toks[s].tmpl = "start"
                    t.tmpl = "end"
            elif x in ("(", "["):
                depth += 1
            elif x in (")", "]"):
                while pending and pending[-1][1] >= depth:
                    pending.pop()
                depth = max(0, depth - 1)
            elif x in ("=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<="):
                prev = toks[i - 1] if i else None
                # '>' '=' that is a '>=' comparison rather than an assignment
                is_ge = (x == "=" and prev is not None and prev.text == ">" and prev.tmpl is None
                         and prev.end == t.pos)
                if not is_ge:
                    depth = 0
                    pending.clear()
            elif x in (";", "{", ":"):
                depth = 0
                pending.clear()
            elif x in ("&&", "||"):
                while pending and pending[-1][1] >= depth:
                    pending.pop()
        i += 1


def _merge_gt(toks: list[Tok]) -> list[Tok]:
    out: list[Tok] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.text == ">" and t.tmpl is None:
            text, end, j = ">", t.end, i + 1
            if j < len(toks) and toks[j].text == ">" and toks[j].tmpl is None and toks[j].pos == end:
                text, end, j = ">>", toks[j].end, j + 1
            if j < len(toks) and toks[j].text == "=" and toks[j].pos == end:
                text, end, j = text + "=", toks[j].end, j + 1
            out.append(Tok("op", text, t.pos, end))
            i = j
            continue
        out.append(t)
        i += 1
    return out


# ---------------------------------------------------------------------------- parser

_BINARY_PREC = [
    ("||",),
    ("&&",),
    ("|",),
    ("^",),
    ("&",),
    ("==", "!=", "<", ">", "<=", ">="),
    ("<<", ">>"),
    ("+", "-"),
    ("*", "/", "%"),
]
_ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}


class Parser:
    def __init__(self, src: str):
        self.src = src
        self.toks = lex(src)
        self.i = 0

    # -- token helpers
    @property
    def tok(self) -> Tok:
        return self.toks[self.i]

    def peek(self, k=1) -> Tok:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def at(self, text) -> bool:
        t = self.tok
        return t.text == text and t.kind != "num"

    def at_tmpl_start(self) -> bool:
        return self.tok.text == "<" and self.tok.tmpl == "start"

    def advance(self) -> Tok:
        t = self.tok
        self.i += 1
        return t

    def eat(self, text) -> bool:
        if self.at(text):
            self.i += 1
            return True
        return False

    def expect(self, text) -> Tok:
        if not self.at(text):
            self.error(f"expected {text!r}, got {self.tok.text!r}")
        return self.advance()

    def ident(self) -> str:
        t = self.tok
        if t.kind != "ident" or t.text in KEYWORDS:
            self.error(f"expected identifier, got {t.text!r}")
        self.i += 1
        return t.text

    def error(self, msg):
        raise WGSLSyntaxError(msg, self.src, self.tok.pos)

    # -- module
    def module(self) -> Module:
        directives, decls = [], []
        while self.tok.kind != "eof":
            if self.at("enable") or self.at("requires") or (
                    self.at("diagnostic") and self.peek().text == "("):
                directives.append(self.directive())
                continue
            if self.eat(";"):
                continue
            decls.append(self.global_decl())
        return Module(directives, decls)

    def directive(self) -> Directive:
        kind = self.advance().text
        start = self.tok.pos
        depth = 0
        while not (self.at(";") and depth == 0):
            if self.tok.kind == "eof":
                self.error("unterminated directive")
            if self.at("("):
                depth += 1
            elif self.at(")"):
                depth -= 1
            self.advance()
        end = self.tok.pos
        self.expect(";")
        body = self.src[start:end]
        # normalise internal whitespace; directive bodies are names, commas, parens and dots
        body = re.sub(r"\s*([(),.])\s*", r"\1", body.strip())
        body = re.sub(r"\s+", " ", body)
        return Directive(kind, body)

    def attributes(self) -> list[Attribute]:
        attrs = []
        while self.at("@"):
            self.advance()
            name = self.advance().text   # attribute names may be keywords (e.g. @const, @diagnostic)
            args = None
            if self.at("("):
                self.advance()
                args = []
                while not self.at(")"):
                    args.append(self.expression())
                    if not self.eat(","):
                        break
                self.expect(")")
            attrs.append(Attribute(name, args))
        return attrs

    def global_decl(self):
        attrs = self.attributes()
        t = self.tok.text
        if t == "struct":
            self.advance()
            name = self.ident()
            self.expect("{")
            members = []
            while not self.at("}"):
                mattrs = self.attributes()
                mname = self.ident()
                self.expect(":")
                mtype = self.type_expr()
                members.append(StructMember(mattrs, mname, mtype))
                if not self.eat(","):
                    break
            self.expect("}")
            self.eat(";")
            return Struct(attrs, name, members)
        if t == "fn":
            return self.function(attrs)
        if t in ("var", "const", "override", "let"):
            d = self.decl(attrs)
            self.expect(";")
            return d
        if t == "alias":
            self.advance()
            name = self.ident()
            self.expect("=")
            ty = self.type_expr()
            self.expect(";")
            return Alias(attrs, name, ty)
        if t == "const_assert":
            self.advance()
            e = self.expression()
            self.expect(";")
            return ConstAssert(e)
        self.error(f"unexpected {t!r} at module scope")

    def function(self, attrs) -> Fn:
        self.expect("fn")
        name = self.ident()
        self.expect("(")
        params = []
        while not self.at(")"):
            pattrs = self.attributes()
            pname = self.ident()
            self.expect(":")
            params.append(Param(pattrs, pname, self.type_expr()))
            if not self.eat(","):
                break
        self.expect(")")
        ret_attrs, ret = [], None
        if self.eat("->"):
            ret_attrs = self.attributes()
            ret = self.type_expr()
        body = self.compound()
        return Fn(attrs, name, params, ret_attrs, ret, body)

    def decl(self, attrs=None) -> Decl:
        kind = self.advance().text
        tmpl = None
        if kind == "var" and self.at_tmpl_start():
            tmpl = self.template_list()
        name = self.ident()
        ty = None
        if self.eat(":"):
            ty = self.type_expr()
        init = None
        if self.eat("="):
            init = self.expression()
        return Decl(attrs or [], kind, tmpl, name, ty, init)

    def type_expr(self) -> Ident:
        name = self.tok.text
        if self.tok.kind != "ident":
            self.error(f"expected type, got {name!r}")
        self.advance()
        tmpl = self.template_list() if self.at_tmpl_start() else None
        return Ident(name, tmpl)

    def template_list(self) -> list:
        self.advance()   # '<'
        args = []
        while not (self.tok.text == ">" and self.tok.tmpl == "end"):
            args.append(self.expression())
            if not self.eat(","):
                break
        if not (self.tok.text == ">" and self.tok.tmpl == "end"):
            self.error("unterminated template list")
        self.advance()
        return args

    # -- statements
    def compound(self, attrs=None) -> Block:
        self.expect("{")
        stmts = []
        while not self.at("}"):
            if self.tok.kind == "eof":
                self.error("unterminated block")
            stmts.append(self.statement())
        self.expect("}")
        return Block(stmts, attrs or [])

    def statement(self):
        attrs = self.attributes()
        t = self.tok.text
        if self.tok.kind == "op":
            if t == ";":
                self.advance()
                return Empty()
            if t == "{":
                return self.compound(attrs)
        else:
            if t == "return":
                self.advance()
                e = None if self.at(";") else self.expression()
                self.expect(";")
                return Return(e)
            if t == "if":
                return self.if_stmt(attrs)
            if t == "switch":
                return self.switch_stmt(attrs)
            if t == "loop":
                return self.loop_stmt(attrs)
            if t == "for":
                return self.for_stmt(attrs)
            if t == "while":
                self.advance()
                cond = self.expression()
                return While(attrs, cond, self.compound())
            if t == "break":
                self.advance()
                if self.at("if"):
                    self.advance()
                    e = self.expression()
                    self.expect(";")
                    return BreakIf(e)
                self.expect(";")
                return Break()
            if t == "continue":
                self.advance()
                self.expect(";")
                return Continue()
            if t == "discard":
                self.advance()
                self.expect(";")
                return Discard()
            if t == "const_assert":
                self.advance()
                e = self.expression()
                self.expect(";")
                return ConstAssert(e)
        s = self.simple_statement()
        self.expect(";")
        return s

    def simple_statement(self):
        """var/let/const declarations, assignments, increments and call statements:
        everything allowed in a for-loop header."""
        t = self.tok.text
        if self.tok.kind == "ident" and t in ("var", "let", "const"):
            return self.decl()
        lhs = self.expression()
        if self.tok.text in _ASSIGN_OPS:
            op = self.advance().text
            return Assign(lhs, op, self.expression())
        if self.at("++") or self.at("--"):
            return IncDec(lhs, self.advance().text)
        return ExprStmt(lhs)

    def if_stmt(self, attrs) -> If:
        self.expect("if")
        cond = self.expression()
        then = self.compound()
        els = None
        if self.eat("else"):
            if self.at("if"):
                els = self.if_stmt([])
            else:
                els = self.compound()
        return If(attrs, cond, then, els)

    def switch_stmt(self, attrs) -> Switch:
        self.expect("switch")
        expr = self.expression()
        body_attrs = self.attributes()
        self.expect("{")
        cases = []
        while not self.at("}"):
            cattrs = self.attributes()
            sels = []
            if self.eat("default"):
                sels.append(None)
            else:
                self.expect("case")
                while not (self.at(":") or self.at("{") or self.at("@")):
                    if self.eat("default"):
                        sels.append(None)
                    else:
                        sels.append(self.expression())
                    if not self.eat(","):
                        break
            self.eat(":")
            battrs = self.attributes()
            cases.append(Case(sels, self.compound(battrs), cattrs))
        self.expect("}")
        return Switch(attrs, expr, body_attrs, cases)

    def loop_stmt(self, attrs) -> Loop:
        self.expect("loop")
        body_attrs = self.attributes()
        self.expect("{")
        stmts, continuing, cont_attrs, break_if = [], None, [], None
        while not self.at("}"):
            if self.at("continuing"):
                self.advance()
                cont_attrs = self.attributes()
                self.expect("{")
                continuing = []
                while not self.at("}"):
                    s = self.statement()
                    continuing.append(s)
                self.expect("}")
                if continuing and isinstance(continuing[-1], BreakIf):
                    break_if = continuing.pop().cond
                continue
            stmts.append(self.statement())
        self.expect("}")
        return Loop(attrs, body_attrs, stmts, continuing, cont_attrs, break_if)

    def for_stmt(self, attrs) -> For:
        self.expect("for")
        self.expect("(")
        init = None if self.at(";") else self.simple_statement()
        self.expect(";")
        cond = None if self.at(";") else self.expression()
        self.expect(";")
        update = None if self.at(")") else self.simple_statement()
        self.expect(")")
        return For(attrs, init, cond, update, self.compound())

    # -- expressions
    def expression(self, level=0):
        if level == len(_BINARY_PREC):
            return self.unary()
        ops = _BINARY_PREC[level]
        left = self.expression(level + 1)
        while self.tok.kind == "op" and self.tok.text in ops and self.tok.tmpl is None:
            op = self.advance().text
            right = self.expression(level + 1)
            left = Binary(op, left, right)
        return left

    def unary(self):
        t = self.tok
        if t.kind == "op" and t.text in ("-", "!", "~", "*", "&"):
            self.advance()
            return Unary(t.text, self.unary())
        return self.postfix(self.primary())

    def primary(self):
        t = self.tok
        if t.kind == "num":
            self.advance()
            return Lit(t.text)
        if t.kind == "ident":
            if t.text in ("true", "false"):
                self.advance()
                return Lit(t.text)
            if t.text in KEYWORDS:
                self.error(f"unexpected keyword {t.text!r}")
            self.advance()
            tmpl = self.template_list() if self.at_tmpl_start() else None
            ident = Ident(t.text, tmpl)
            if self.at("("):
                self.advance()
                args = []
                while not self.at(")"):
                    args.append(self.expression())
                    if not self.eat(","):
                        break
                self.expect(")")
                return Call(ident, args)
            return ident
        if self.eat("("):
            e = self.expression()
            self.expect(")")
            return e
        self.error(f"unexpected {t.text!r} in expression")

    def postfix(self, e):
        while True:
            if self.at("."):
                self.advance()
                e = Member(e, self.advance().text)
            elif self.at("["):
                self.advance()
                idx = self.expression()
                self.expect("]")
                e = Index(e, idx)
            else:
                return e


def parse(src: str) -> Module:
    return Parser(src).module()
