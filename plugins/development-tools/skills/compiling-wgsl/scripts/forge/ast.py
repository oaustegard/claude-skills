"""WGSL syntax tree. Plain classes with __slots__; ``sym`` slots are filled by
``forge.scope.resolve`` and point at the Symbol a name refers to."""
from __future__ import annotations


class Node:
    __slots__ = ()
    _fields: tuple = ()

    def __repr__(self):
        args = ", ".join(f"{f}={getattr(self, f)!r}" for f in self._fields)
        return f"{type(self).__name__}({args})"

    def __eq__(self, other):
        return type(self) is type(other) and all(
            getattr(self, f) == getattr(other, f) for f in self._fields)

    __hash__ = object.__hash__


def _node(name, fields, extra=()):
    def __init__(self, *args):
        for f, v in zip(fields, args):
            setattr(self, f, v)
        for f in extra:
            setattr(self, f, None)
    cls = type(name, (Node,), {"__slots__": tuple(fields) + tuple(extra), "_fields": tuple(fields),
                               "__init__": __init__})
    return cls


# -- module level
Module = _node("Module", ("directives", "decls"))
Directive = _node("Directive", ("kind", "body"))           # enable / requires / diagnostic
Attribute = _node("Attribute", ("name", "args"))           # args: list[expr] | None
Struct = _node("Struct", ("attrs", "name", "members"), ("sym",))
StructMember = _node("StructMember", ("attrs", "name", "type"))
Fn = _node("Fn", ("attrs", "name", "params", "ret_attrs", "ret", "body"), ("sym",))
Param = _node("Param", ("attrs", "name", "type"), ("sym",))
# var / let / const / override, at module or function scope. tmpl: var<space, access>
Decl = _node("Decl", ("attrs", "kind", "tmpl", "name", "type", "init"), ("sym",))
Alias = _node("Alias", ("attrs", "name", "type"), ("sym",))
ConstAssert = _node("ConstAssert", ("expr",))

# -- statements
Block = _node("Block", ("stmts", "attrs"))
Return = _node("Return", ("expr",))
If = _node("If", ("attrs", "cond", "then", "els"))           # els: Block | If | None
Switch = _node("Switch", ("attrs", "expr", "body_attrs", "cases"))
Case = _node("Case", ("selectors", "body", "attrs"))        # selector None = default
Loop = _node("Loop", ("attrs", "body_attrs", "stmts", "continuing", "cont_attrs", "break_if"))
For = _node("For", ("attrs", "init", "cond", "update", "body"))
While = _node("While", ("attrs", "cond", "body"))
Break = _node("Break", ())
BreakIf = _node("BreakIf", ("cond",))
Continue = _node("Continue", ())
Discard = _node("Discard", ())
Assign = _node("Assign", ("lhs", "op", "rhs"))
IncDec = _node("IncDec", ("lhs", "op"))
ExprStmt = _node("ExprStmt", ("expr",))
Empty = _node("Empty", ())

# -- expressions
Ident = _node("Ident", ("name", "tmpl"), ("sym",))          # also every type expression
Call = _node("Call", ("callee", "args"))                    # callee: Ident
Lit = _node("Lit", ("text",))
Unary = _node("Unary", ("op", "expr"))
Binary = _node("Binary", ("op", "left", "right"), ("paren",))
Member = _node("Member", ("expr", "name"))
Index = _node("Index", ("expr", "index"))

EXPR_TYPES = (Ident, Call, Lit, Unary, Binary, Member, Index)


def children(node):
    """Direct child nodes, in source order."""
    for f in node._fields:
        v = getattr(node, f)
        if isinstance(v, Node):
            yield v
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, Node):
                    yield x


def walk(node):
    yield node
    for c in children(node):
        yield from walk(c)
