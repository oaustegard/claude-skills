"""Deterministic structural linter for composing-html output.

No LLM, no network, stdlib only. Catches the ways body content breaks *out*
of the composer's fixed design system or miswires its interactive hooks —
the inverse of a freehand design linter. The composer supplies a vetted token
palette and type stacks; this checker flags content that bypasses them or
wires `base.js` behaviours (tabs / binds / sortables) to nothing.

Each rule carries a stable `id` that is anchored in SKILL.md (`<!-- rule:ID -->`)
so the teaching and the enforcement stay linked.

Public API:
    check_html(html, *, fragment=None) -> list[Finding]
    format_findings(findings) -> str

Exit-code contract (CLI): 1 if any error-severity finding, else 0.

Deliberately NOT checked in v1: colour-contrast ratios. The token pairs are
pre-vetted, and contrast on author-introduced custom pairs needs colour math +
rendering that a regex pass can't do without false positives. Deferred.
"""

from __future__ import annotations

import html.parser as _hp
import re
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# canonical design tokens (mirror of assets/base.css :root)                   #
# --------------------------------------------------------------------------- #

BASE_TOKENS = {
    "ivory", "paper", "slate", "clay", "clay-d", "oat", "olive", "rust", "moss",
    "g100", "g150", "g200", "g300", "g500", "g700",
    "border", "border-soft",
    "radius", "radius-sm", "radius-lg",
    "shadow-card", "shadow-pop",
    "serif", "sans", "mono",
    "ok", "warn", "err", "info",
}

# colours that are fine as literals (not palette drift)
_COLOR_KEYWORD_OK = {"transparent", "currentcolor", "inherit", "none", "initial", "unset"}

_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_FUNC_COLOR_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla)\s*\(", re.I)
_VAR_RE = re.compile(r"var\(\s*--([a-z0-9-]+)", re.I)
_FONT_FAMILY_RE = re.compile(r"font-family\s*:", re.I)
_FONT_SIZE_RE = re.compile(r"font-size\s*:", re.I)


# --------------------------------------------------------------------------- #
# findings                                                                    #
# --------------------------------------------------------------------------- #

@dataclass
class Finding:
    rule: str
    severity: str          # "error" | "warn"
    message: str
    detail: str = ""

    def __str__(self) -> str:
        tail = f" — {self.detail}" if self.detail else ""
        return f"[{self.severity}] {self.rule}: {self.message}{tail}"


# --------------------------------------------------------------------------- #
# minimal DOM (parent pointers; enough for structural rules)                  #
# --------------------------------------------------------------------------- #

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
         "meta", "param", "source", "track", "wbr"}


@dataclass
class Node:
    tag: str
    attrs: dict
    parent: Optional["Node"] = None
    children: list = field(default_factory=list)

    @property
    def classes(self) -> set:
        return set((self.attrs.get("class") or "").split())


class _DOM(_hp.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {})
        self._stack = [self.root]
        self.nodes: list[Node] = []

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self._stack[-1])
        self._stack[-1].children.append(node)
        self.nodes.append(node)
        if tag not in _VOID:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self._stack[-1])
        self._stack[-1].children.append(node)
        self.nodes.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                break


def _parse(html: str) -> _DOM:
    dom = _DOM()
    dom.feed(html)
    return dom


def _ancestors(node: Node):
    p = node.parent
    while p is not None:
        yield p
        p = p.parent


# --------------------------------------------------------------------------- #
# rules                                                                       #
# --------------------------------------------------------------------------- #

def _is_fragment(html: str) -> bool:
    head = html.lstrip()[:200].lower()
    return not (head.startswith("<!doctype") or head.startswith("<html") or "<html" in head[:200])


def _rule_chrome_leak(html: str, dom: _DOM, fragment: bool, out: list):
    # SKILL.md output rule 1: body_html must never contain page chrome.
    # Only meaningful for fragments — a full artifact is *expected* to have it.
    if not fragment:
        return
    for node in dom.nodes:
        if node.tag in ("html", "head", "link"):
            out.append(Finding("chrome-leak", "error",
                               f"<{node.tag}> in body content",
                               "the composer supplies page chrome; body_html must not"))
        elif node.tag in ("style", "script"):
            out.append(Finding("chrome-leak", "warn",
                               f"top-level <{node.tag}> in body content",
                               "prefer extra_css / extra_js spec fields"))


def _defined_tokens(html: str, dom: _DOM) -> set:
    """Tokens legitimately available: base palette + --bind-* (created by
    data-bind hooks) + any custom --x declared in an author <style>."""
    defined = set(BASE_TOKENS)
    for m in re.finditer(r"data-bind\s*=\s*[\"']([a-z0-9_-]+)", html, re.I):
        defined.add("bind-" + m.group(1))
    # author-declared custom properties:  --foo:
    for m in re.finditer(r"(?<![a-z0-9-])--([a-z0-9-]+)\s*:", html, re.I):
        defined.add(m.group(1))
    return defined


def _rule_undefined_token(html: str, dom: _DOM, fragment: bool, out: list):
    defined = _defined_tokens(html, dom)
    seen = set()
    for m in _VAR_RE.finditer(html):
        name = m.group(1).lower()
        if name not in defined and name not in seen:
            seen.add(name)
            out.append(Finding("undefined-token", "error",
                               f"var(--{name}) references an undefined token",
                               "typo, or a token that isn't in the palette / not declared here"))


def _style_strings(dom: _DOM):
    for node in dom.nodes:
        st = node.attrs.get("style")
        if st:
            yield node, st


def _rule_hardcoded_color(html: str, dom: _DOM, fragment: bool, out: list):
    reported = 0
    for node, st in _style_strings(dom):
        if _HEX_RE.search(st) or _FUNC_COLOR_RE.search(st):
            reported += 1
            if reported <= 8:
                out.append(Finding("hardcoded-color", "warn",
                                   f"literal colour in style= on <{node.tag}>",
                                   "use a palette token, e.g. var(--clay), var(--g500)"))
    if reported > 8:
        out.append(Finding("hardcoded-color", "warn",
                           f"...and {reported - 8} more literal-colour style attributes"))


def _rule_inline_typography(html: str, dom: _DOM, fragment: bool, out: list):
    for node, st in _style_strings(dom):
        if _FONT_FAMILY_RE.search(st):
            out.append(Finding("inline-typography", "warn",
                               f"font-family in style= on <{node.tag}>",
                               "use the type stacks: var(--serif), var(--sans), var(--mono)"))
        if _FONT_SIZE_RE.search(st):
            out.append(Finding("inline-typography", "warn",
                               f"font-size in style= on <{node.tag}>",
                               "prefer the heading scale / existing type sizes"))


def _rule_nested_card(html: str, dom: _DOM, fragment: bool, out: list):
    for node in dom.nodes:
        if "card" in node.classes:
            if any("card" in a.classes for a in _ancestors(node)):
                out.append(Finding("nested-card", "warn",
                                   f"<{node.tag} class=card> nested inside another .card",
                                   "card-in-card; flatten or use a plain container"))


def _rule_broken_tabs(html: str, dom: _DOM, fragment: bool, out: list):
    targets = [(n, n.attrs.get("data-target")) for n in dom.nodes if n.attrs.get("data-target")]
    panel_ids = {n.attrs.get("data-id") for n in dom.nodes if "tab-panel" in n.classes}
    panel_ids.discard(None)
    target_vals = {t for _, t in targets}
    for node, t in targets:
        if t not in panel_ids:
            out.append(Finding("broken-tabs", "error",
                               f'data-target="{t}" has no matching .tab-panel[data-id="{t}"]',
                               "tab button wired to a missing panel"))
    for n in dom.nodes:
        if "tab-panel" in n.classes:
            pid = n.attrs.get("data-id")
            if pid and pid not in target_vals:
                out.append(Finding("broken-tabs", "warn",
                                   f'.tab-panel[data-id="{pid}"] has no button targeting it',
                                   "orphan panel — unreachable"))


def _rule_broken_bind(html: str, dom: _DOM, fragment: bool, out: list):
    binds = {n.attrs.get("data-bind") for n in dom.nodes if n.attrs.get("data-bind")}
    outs = {n.attrs.get("data-out") for n in dom.nodes if n.attrs.get("data-out")}
    var_binds = {m.group(1)[5:] for m in _VAR_RE.finditer(html)
                 if m.group(1).lower().startswith("bind-")}
    for b in binds:
        if b not in outs and b not in var_binds:
            out.append(Finding("broken-bind", "warn",
                               f'data-bind="{b}" has no consumer',
                               f'no [data-out="{b}"] and no var(--bind-{b})'))
    for o in outs:
        if o not in binds:
            out.append(Finding("broken-bind", "warn",
                               f'[data-out="{o}"] has no matching data-bind="{o}"',
                               "output element will never update"))


def _rule_broken_sortable(html: str, dom: _DOM, fragment: bool, out: list):
    for node in dom.nodes:
        if "data-sortable" in node.attrs:
            # descendants
            stack = list(node.children)
            has_draggable = False
            while stack:
                cur = stack.pop()
                if (cur.attrs.get("draggable") or "").lower() == "true":
                    has_draggable = True
                    break
                stack.extend(cur.children)
            if not has_draggable:
                out.append(Finding("broken-sortable", "warn",
                                   f"<{node.tag} data-sortable> has no draggable children",
                                   'add draggable="true" to the reorderable items'))


def _rule_heading_skip(html: str, dom: _DOM, fragment: bool, out: list):
    prev = None
    for node in dom.nodes:
        if len(node.tag) == 2 and node.tag[0] == "h" and node.tag[1].isdigit():
            lvl = int(node.tag[1])
            if prev is not None and lvl > prev + 1:
                out.append(Finding("heading-skip", "warn",
                                   f"heading jumps h{prev} -> h{lvl}",
                                   "don't skip heading levels"))
            prev = lvl


def _rule_img_no_alt(html: str, dom: _DOM, fragment: bool, out: list):
    for node in dom.nodes:
        if node.tag == "img" and "alt" not in node.attrs:
            out.append(Finding("img-no-alt", "warn",
                               "<img> without alt attribute",
                               'add alt="" (empty for decorative)'))


_RULES = [
    _rule_chrome_leak,
    _rule_undefined_token,
    _rule_hardcoded_color,
    _rule_inline_typography,
    _rule_nested_card,
    _rule_broken_tabs,
    _rule_broken_bind,
    _rule_broken_sortable,
    _rule_heading_skip,
    _rule_img_no_alt,
]


# --------------------------------------------------------------------------- #
# public                                                                      #
# --------------------------------------------------------------------------- #

def check_html(html: str, *, fragment: Optional[bool] = None) -> list[Finding]:
    if fragment is None:
        fragment = _is_fragment(html)
    dom = _parse(html)
    out: list[Finding] = []
    for rule in _RULES:
        rule(html, dom, fragment, out)
    return out


def format_findings(findings: list[Finding]) -> str:
    if not findings:
        return "OK — no findings."
    errs = sum(1 for f in findings if f.severity == "error")
    warns = sum(1 for f in findings if f.severity == "warn")
    lines = [str(f) for f in findings]
    lines.append(f"\n{errs} error(s), {warns} warning(s).")
    return "\n".join(lines)


def has_errors(findings: list[Finding]) -> bool:
    return any(f.severity == "error" for f in findings)
