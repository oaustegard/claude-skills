#!/usr/bin/env python3
"""totality_lint.py — find tests that enumerate a domain by copying it.

A test that loops a hand-written list passes its runner and proves nothing
about completeness. When the same members also exist as a registry in the
source — a dict, a set, a tuple, an Enum — the list is a *copy*, and the copy
drifts the moment someone adds a member to the registry and not to the test.
Nothing goes red. The suite still says 267 passed.

Measured on `oaustegard/remex` (2026-08-24): adding a fourth member to
`ROTATION_CODES` with nothing behind it left the entire 267-test suite green.
Only a test that looped the registry itself caught it.

This reports two findings:

  sampled-domain   a test iterates a literal whose members are a strict subset
                   of a source registry's members. The missing members are
                   named, because those are the ones nothing covers.

  no-floor         a test iterates a live registry with no length assertion
                   anywhere in the file. A registry that collapses to zero
                   makes the loop range over nothing and pass vacuously.

Adapted from the meta-oracle in daniloc/coherence (`src/oracle-domain.ts`,
`analyzeOracle`), which classifies an oracle's iteration root as LIVE or
LITERAL by parsing the oracle's own AST. Three deliberate differences, each
from something the trial of that tool turned up:

  * **Report, not gate.** Its parity arm refuses a correct oracle that binds
    the domain to a local name first (`d = set(REGISTRY); for x in sorted(d)`),
    against a README claiming the analyzer never false-fails. A gate that
    false-fails gets switched off; an advisory gets read. `--strict` opts in.
  * **Join on membership, not on names.** `[1, 2, 3, 4, 8]` and
    `SUPPORTED_BITS` share no token. What ties them is that the literal's
    members are a subset of the registry's, so that is the join key. No
    naming convention is assumed, and none is required.
  * **No spec files.** Coherence needs a `*.spec.md` declaring the claim
    before it will analyse anything. This needs a path.

Acknowledgement is first-class, on the same principle as `memory_lint.py`:
a partial domain is often correct (`save_params` legitimately accepts two of
three rotations). Say so on the test and it stops being a finding:

    # totality: partial — mojo has no construction for "none"
    @pytest.mark.parametrize("rotation", ["haar", "rht"])
    def test_save_params_accepts_every_mojo_rotation(...):

And a suppression must not become a silence: an acknowledgement on a test that
now covers the whole domain is reported in its own right (`stale-ack`).

    python3 scripts/totality_lint.py <path>            # the report
    python3 scripts/totality_lint.py <path> --json     # machine-readable
    python3 scripts/totality_lint.py <path> --strict   # exit 1 if any finding
    python3 scripts/totality_lint.py --selftest        # fixtures, no repo

Python only. The registry and literal extractors are the language-specific
half (`_registries_py`, `_domains_py`); the join, the acknowledgement handling
and the report are not. TypeScript is not covered — a `_registries_ts` pair
built on tree-sitter would slot in beside them.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Iterable

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".tox", "site-packages", ".coherence",
    ".ruff_cache",
}

#: A path is a test file if any of these appear in it. Registries are read from
#: NON-test files only: a list defined in a test file and looped by that same
#: test file is a fixture, not a copied domain, and treating it as a registry is
#: the single largest source of false positives.
TEST_MARKERS = ("test_", "_test.", "/tests/", "/test/", "conftest.py")

#: Fewer members than this and a "domain" is a pair of examples, not an
#: enumeration. Raising it trades recall for precision; 3 keeps
#: `{"haar", "rht", "none"}` in scope, which is the motivating case.
MIN_REGISTRY = 3

#: A literal below this is not plausibly a copy of anything.
MIN_LITERAL = 2

#: `partial` excuses a hand-list. `ratchet` ASSERTS one: the members named are a
#: floor the registry must keep containing, and the linter checks that rather
#: than taking the marker's word for it. Enumeration and a ratchet are
#: complementary, not a ladder — see `_ratchet_findings`.
ACK_KINDS = ("partial", "sampled", "ratchet")
_ACK_ALT = "|".join(ACK_KINDS)
ACK_RE = re.compile(rf"#\s*totality:\s*({_ACK_ALT})\b[ \t]*[-—:]?[ \t]*(.*)")
ACK_DOC_RE = re.compile(rf"^\s*totality:\s*({_ACK_ALT})\b[ \t]*[-—:]?[ \t]*(.*)",
                        re.M)

Member = str | int | float | bool


@dataclass(frozen=True)
class Registry:
    """An enumerated collection defined in source (not test) code."""

    name: str
    members: frozenset
    path: str
    line: int
    kind: str  # dict | set | list | tuple | enum

    @property
    def module(self) -> str:
        return self.path.replace("\\", "/").removesuffix(".py").replace("/", ".")

    @property
    def pkg(self) -> str:
        return self.path.replace("\\", "/").split("/", 1)[0].removesuffix(".py")


@dataclass
class Domain:
    """A collection a test iterates, and how it got hold of it."""

    path: str
    line: int
    test: str
    live: bool
    members: frozenset | None  # None when live
    symbol: str | None  # the registry the iteration roots in, when known
    how: str  # parametrize | for | comprehension
    alias: str | None = None  # the name actually written at the loop, if different
    candidates: list = field(default_factory=list)  # every name it could address

    def lookup_names(self) -> list:
        """Names to try against the registry table, best first.

        Candidates before the resolved root: a test that reaches its subject
        through an importlib-loaded module writes `tl.SKIP_DIRS`, and following
        the local `tl` through the file's own constants lands on `_SPEC` — true,
        useless, and it shadows the name that actually matters.
        """
        return list(dict.fromkeys(
            [c for c in self.candidates if c]
            + [n for n in (self.symbol, self.alias) if n]
        ))
    ack: tuple[str, str] | None = None  # (kind, reason)


@dataclass
class Finding:
    kind: str
    path: str
    line: int
    test: str
    detail: str
    missing: list = field(default_factory=list)
    registry: str | None = None


# --------------------------------------------------------------------------
# extraction — the language-specific half
# --------------------------------------------------------------------------


def _const_members(node: ast.AST) -> frozenset | None:
    """Members of a literal collection, or None if it is not one.

    A dict contributes its KEYS: a name-to-code table is enumerated by name,
    which is what a test parametrizes over.
    """
    if isinstance(node, ast.Dict):
        items = node.keys
    elif isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        items = node.elts
    elif isinstance(node, ast.Call):
        # set([...]) / frozenset([...]) / tuple([...]) / list([...])
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
        if name in {"set", "frozenset", "tuple", "list"} and len(node.args) == 1:
            return _const_members(node.args[0])
        return None
    else:
        return None

    out = []
    for it in items:
        if it is None:  # `{**other}` in a dict
            return None
        if not isinstance(it, ast.Constant):
            return None
        if not isinstance(it.value, (str, int, float, bool)):
            return None
        out.append(it.value)
    return frozenset(out) if out else None


def _is_test_path(path: str) -> bool:
    p = path.replace("\\", "/")
    return any(m in p for m in TEST_MARKERS)


def _registries_py(tree: ast.Module, path: str) -> list[Registry]:
    """Module-level and class-level enumerated collections."""
    found: list[Registry] = []

    def enum_bases(cls: ast.ClassDef) -> bool:
        for b in cls.bases:
            n = b.id if isinstance(b, ast.Name) else getattr(b, "attr", "")
            if n in {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"}:
                return True
        return False

    def scan_assign(node, qualifier: str = ""):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            if not isinstance(t, ast.Name):
                continue
            members = _const_members(node.value)
            if members is None or len(members) < MIN_REGISTRY:
                continue
            kind = {
                ast.Dict: "dict", ast.Set: "set",
                ast.List: "list", ast.Tuple: "tuple",
            }.get(type(node.value), "set")
            found.append(Registry(
                name=qualifier + t.id, members=members, path=path,
                line=node.lineno, kind=kind,
            ))

    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            scan_assign(node)
        elif isinstance(node, ast.ClassDef):
            if enum_bases(node):
                names = [
                    t.id
                    for b in node.body if isinstance(b, ast.Assign)
                    for t in b.targets if isinstance(t, ast.Name)
                ]
                if len(names) >= MIN_REGISTRY:
                    found.append(Registry(
                        name=node.name, members=frozenset(names), path=path,
                        line=node.lineno, kind="enum",
                    ))
            for b in node.body:
                if isinstance(b, (ast.Assign, ast.AnnAssign)) and getattr(b, "value", None):
                    scan_assign(b, qualifier=node.name + ".")
    return found


def _module_consts(tree: ast.Module) -> dict[str, ast.AST]:
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                out[node.targets[0].id] = node.value
    return out


def _imported_names(tree: ast.Module) -> set[str]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                out.add(a.asname or a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                out.add((a.asname or a.name).split(".")[0])
    return out


def _imported_modules(tree: ast.Module) -> set[str]:
    """Dotted module paths this file imports, plus each of their prefixes.

    `from remex.packing import SUPPORTED_BITS` contributes `remex.packing` and
    `remex`. This is what ties a test to the registries it could plausibly be
    copying — see `_reachable`.
    """
    out: set[str] = set()

    def add(mod: str | None):
        if not mod:
            return
        parts = mod.split(".")
        for i in range(1, len(parts) + 1):
            out.add(".".join(parts[:i]))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            add(node.module)
        elif isinstance(node, ast.Import):
            for a in node.names:
                add(a.name)
    return out


def _symbol_candidates(node: ast.AST) -> list[str]:
    """Names a domain iteration could be addressing, best first.

    `_root_symbol` peels an attribute down to its object, so `tl.SKIP_DIRS`
    roots in `tl` — the module, not the registry. That is right for
    `q.rotations()` and wrong for `mod.REGISTRY`, and this repository's own
    tests take the second shape: they load the module under test through
    `importlib` and reach its registries as attributes. So offer the attribute
    name too and let the caller match whichever it recognises.
    """
    out: list[str] = []
    seen = 0
    cur = node
    while seen < 8:
        seen += 1
        if isinstance(cur, ast.Attribute):
            out.append(cur.attr)
            cur = cur.value
            continue
        if isinstance(cur, ast.Call):
            cur = cur.args[0] if cur.args else cur.func
            continue
        if isinstance(cur, (ast.Subscript, ast.Starred)):
            cur = cur.value
            continue
        break
    root = _root_symbol(node)
    if root:
        out.append(root)
    # Preserve order, drop duplicates.
    return list(dict.fromkeys(out))


def _root_symbol(node: ast.AST) -> str | None:
    """Peel `sorted(X)`, `list(X.keys())`, `X.values()` down to `X`."""
    seen = 0
    while seen < 8:
        seen += 1
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            node = node.value
            continue
        if isinstance(node, ast.Call):
            if node.args:
                node = node.args[0]
                continue
            node = node.func
            continue
        if isinstance(node, (ast.Subscript, ast.Starred)):
            node = node.value
            continue
        return None
    return None


def _ack_for(src_lines: list[str], node: ast.AST) -> tuple[str, str] | None:
    """An acknowledgement comment above the test, or in its docstring."""
    start = min(
        [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]
    )
    for ln in range(max(1, start - 4), start):
        m = ACK_RE.search(src_lines[ln - 1])
        if m:
            return (m.group(1), m.group(2).strip())
    doc = ast.get_docstring(node) if isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    ) else None
    if doc:
        m = ACK_DOC_RE.search(doc)
        if m:
            return (m.group(1), m.group(2).strip())
    return None


def _domains_py(tree: ast.Module, path: str, src: str) -> list[Domain]:
    """Every collection a test function iterates."""
    consts = _module_consts(tree)
    imported = _imported_names(tree)
    lines = src.splitlines()
    out: list[Domain] = []

    def classify(value: ast.AST) -> tuple[bool, frozenset | None, str | None, str | None]:
        """-> (live, members, root symbol, local alias).

        The alias matters for the floor check: a test that binds
        `LIVE = sorted(REGISTRY)` and asserts `len(LIVE) >= 3` has a floor,
        even though the iteration roots in `REGISTRY`.
        """
        members = _const_members(value)
        if members is not None:
            return (False, members, None, None)
        cands = _symbol_candidates(value)
        sym = cands[0] if cands else None
        if sym is None:
            return (True, None, None, None)  # unknown shape: assume live, never fail
        sym = next((c for c in cands if c in consts), sym)
        if sym in consts:
            inner = _const_members(consts[sym])
            if inner is not None:
                return (False, inner, sym, None)
            root = _root_symbol(consts[sym])
            return (True, None, root or sym, sym)
        return (True, None, sym, None)

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not fn.name.startswith("test"):
            continue
        ack = _ack_for(lines, fn)

        for dec in fn.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            if _root_symbol(dec.func) != "pytest" and getattr(
                dec.func, "attr", ""
            ) != "parametrize":
                continue
            if getattr(dec.func, "attr", "") != "parametrize" or len(dec.args) < 2:
                continue
            argnames = dec.args[0]
            if not (isinstance(argnames, ast.Constant)
                    and isinstance(argnames.value, str)
                    and "," not in argnames.value):
                continue  # multi-parameter tables are out of scope
            live, members, sym, alias = classify(dec.args[1])
            out.append(Domain(path, dec.lineno, fn.name, live, members, sym,
                              "parametrize", alias, _symbol_candidates(
                              dec.args[1]), ack))

        for node in ast.walk(fn):
            if isinstance(node, ast.For):
                live, members, sym, alias = classify(node.iter)
                out.append(Domain(path, node.lineno, fn.name, live, members,
                                  sym, "for", alias, _symbol_candidates(
                              node.iter), ack))
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp,
                                   ast.DictComp)):
                for gen in node.generators:
                    live, members, sym, alias = classify(gen.iter)
                    out.append(Domain(path, node.lineno, fn.name, live, members,
                                      sym, "comprehension", alias, _symbol_candidates(
                              gen.iter), ack))
    return out


def _has_floor(tree: ast.Module, *symbols: str | None) -> bool:
    """Any `len(<symbol>) <op> n` comparison anywhere in the module.

    Several names can stand for one domain — the registry and whatever local
    the test bound it to — so a floor on any of them counts.
    """
    wanted = {s for s in symbols if s}
    if not wanted:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        if isinstance(left, ast.Call) and _root_symbol(left.func) == "len":
            if left.args and _root_symbol(left.args[0]) in wanted:
                return True
    return False


# --------------------------------------------------------------------------
# the join — language-independent
# --------------------------------------------------------------------------


def _reachable(reg: Registry, test_path: str, imports: set[str]) -> bool:
    """Could this test plausibly be copying THIS registry?

    Without this, a numeric literal matches any numeric registry anywhere in the
    tree. Measured on `oaustegard/experiments`, a monorepo of unrelated
    projects: 3 of 4 findings joined a test in `discrepancy/` to registries in
    `kb-k-sweep/` and `remex-vs-higgs-ablation/`, purely because small integer
    sets collide. Two ways to be reachable, either sufficient:

      * the test imports the registry's module or its package
      * they sit under the same top-level directory
    """
    if reg.module in imports or reg.pkg in imports:
        return True
    tail = reg.module.rsplit(".", 1)[-1]
    if any(i.split(".")[-1] == tail for i in imports):
        return True
    # tests/test_totality_lint.py <-> scripts/totality_lint.py. The convention
    # this repository actually uses, and the one importlib-loaded tests need:
    # they have no import statement naming the module they exercise.
    stem = pathlib.PurePath(test_path).stem
    for prefix, suffix in (("test_", ""), ("", "_test")):
        if prefix and stem.startswith(prefix):
            stem = stem[len(prefix):]
        if suffix and stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    if stem == pathlib.PurePath(reg.path).stem:
        return True
    test_pkg = test_path.replace("\\", "/").split("/", 1)[0].removesuffix(".py")
    return test_pkg == reg.pkg


def _best_registry(members: frozenset, regs: Iterable[Registry]) -> Registry | None:
    """The smallest registry that strictly contains these members.

    Smallest, because a literal contained by both a 4-member and a 40-member
    registry is far more likely to be a copy of the 4.
    """
    cands = [r for r in regs if members < r.members]
    if not cands:
        return None
    return min(cands, key=lambda r: (len(r.members), r.path, r.line))


def _nearest_registry(d, regs) -> tuple | None:
    """(registry, members of the ratchet it no longer holds).

    An empty second element means the ratchet is intact — it pins the whole
    domain rather than a strict subset of it.

    A ratchet is a hand-list asserting the domain keeps containing it. That is
    the direction an enumeration cannot see: a totality oracle loops whatever
    the domain currently is, so a member LEAVING is trivially green. Measured on
    `oaustegard/remex`: substituting one member for another, keeping cardinality
    and keeping a second spelling of the domain in agreement, passed the domain
    floor, the enumeration and the parity check — five green tests while a
    supported rotation silently left.

    Match on overlap rather than containment, because containment is exactly
    what broke.
    """
    best, best_key = None, None
    for r in regs:
        overlap = len(d.members & r.members)
        if overlap < MIN_LITERAL:
            continue
        # Most overlap wins; ties break on the smaller registry, then on a
        # stable address, so one report does not reorder between runs.
        key = (-overlap, len(r.members), r.path, r.line)
        if best_key is None or key < best_key:
            best, best_key = r, key
    if best is None:
        return None
    return (best, sorted(d.members - best.members, key=repr))


def scan(root: pathlib.Path) -> tuple[list[Finding], dict]:
    src_files, test_files = [], []
    for p in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = str(p.relative_to(root))
        (test_files if _is_test_path(rel) else src_files).append((p, rel))

    registries: list[Registry] = []
    for p, rel in src_files:
        try:
            registries.extend(_registries_py(ast.parse(p.read_text(errors="replace")), rel))
        except (SyntaxError, ValueError, OSError):
            continue

    findings: list[Finding] = []
    #: registry name -> the ratchet domains pinning it
    ratcheted: dict[str, list] = {}
    #: registry name -> the domains enumerating it live
    enumerated: dict[str, list] = {}
    domains_seen = 0
    for p, rel in test_files:
        try:
            src = p.read_text(errors="replace")
            tree = ast.parse(src)
        except (SyntaxError, ValueError, OSError):
            continue
        imports = _imported_modules(tree)
        visible = [r for r in registries if _reachable(r, rel, imports)]
        vis_by_name: dict[str, Registry] = {}
        for r in visible:
            for key in {r.name, r.name.rsplit(".", 1)[-1]}:
                vis_by_name.setdefault(key, r)

        for d in _domains_py(tree, rel, src):
            domains_seen += 1
            if d.live:
                # Only a name we independently recognised as a registry earns a
                # no-floor finding. Firing on every `for x in <local>` produced 27
                # findings on remex, all noise — numpy arrays, query matrices, loop
                # counters. A wall of candidates is worse than silence.
                reg = next(
                    (vis_by_name[c] for c in d.lookup_names() if c in vis_by_name),
                    None,
                )
                if reg and not _has_floor(tree, d.symbol, d.alias, reg.name,
                                          reg.name.rsplit(".", 1)[-1]):
                    findings.append(Finding(
                        "no-floor", d.path, d.line, d.test,
                        f"iterates `{reg.name}` ({reg.kind}, {reg.path}:"
                        f"{reg.line}, {len(reg.members)} members) with no "
                        f"`len(...) >= n` assertion in this file — vacuous if "
                        f"it empties",
                        registry=reg.name,
                    ))
                if reg:
                    enumerated.setdefault(reg.name, []).append(d)
                if d.ack and reg:
                    findings.append(Finding(
                        "stale-ack", d.path, d.line, d.test,
                        f"acknowledged as {d.ack[0]} ({d.ack[1] or 'no reason given'}), "
                        f"but it iterates a live domain — the ack no longer suppresses "
                        f"anything",
                    ))
                continue

            if d.members is None or len(d.members) < MIN_LITERAL:
                continue
            reg = _best_registry(d.members, visible)
            if reg is None:
                if d.ack and d.ack[0] == "ratchet":
                    # No strict superset, so either the ratchet pins the whole
                    # domain (intact) or a member has left (broken).
                    hit = _nearest_registry(d, visible)
                    if hit:
                        reg, left = hit
                        for r in visible:
                            if d.members <= r.members:
                                ratcheted.setdefault(r.name, []).append(d)
                        ratcheted.setdefault(reg.name, []).append(d)
                        if left:
                            findings.append(Finding(
                                "ratchet-broken", d.path, d.line, d.test,
                                f"pins {len(d.members)} member(s) of "
                                f"`{reg.name}`, and the registry no longer "
                                f"contains all of them — a member left without "
                                f"the ratchet being retired",
                                missing=left, registry=reg.name,
                            ))
                continue
            missing = sorted(reg.members - d.members, key=repr)
            if d.ack and d.ack[0] == "ratchet":
                # Pin EVERY registry the hand-list is a floor for. One domain is
                # often spelled twice (`ROTATION_CODES` for the on-disk byte,
                # `Quantizer.ROTATIONS` for the constructor), and a ratchet over
                # its members holds each of them.
                for r in visible:
                    if d.members <= r.members:
                        ratcheted.setdefault(r.name, []).append(d)
                # And FALL THROUGH. A ratchet is a statement about the domain
                # SHRINKING; it says nothing about the members it never listed,
                # so a partial ratchet leaves those exactly as uncovered as an
                # unmarked hand-list does. Suppressing the finding here would
                # make the marker a laundering channel — the same escape hatch
                # this tool's own notes criticise `via guard` for being in
                # `daniloc/coherence`, reproduced one day later. Verified 2026-08-25:
                # `# totality: ratchet` over 2 of 3 members silenced the report
                # entirely and checked nothing about the third.
            elif d.ack:
                continue
            others = sum(
                1 for r in visible
                if d.members < r.members and len(r.members) == len(reg.members)
            ) - 1
            also = f" (+{others} registry/ies of the same size also contain it)" if others else ""
            pinned = " (pinned as a ratchet, which covers only shrink)" \
                if d.ack and d.ack[0] == "ratchet" else ""
            findings.append(Finding(
                "sampled-domain", d.path, d.line, d.test,
                f"{d.how} over a literal of {len(d.members)}{pinned}, but "
                f"`{reg.name}` ({reg.kind}, {reg.path}:{reg.line}) has "
                f"{len(reg.members)}{also}",
                missing=missing, registry=reg.name,
            ))

    # The complement Yep named: enumeration proves every CURRENT member is
    # handled and is structurally blind to the domain narrowing, because it
    # loops whatever the domain now is. A ratchet is the other direction.
    # A registry with no floor AND no ratchet produced two findings on the same
    # line saying overlapping things — 3 of 3 on `claude-workspace`, which a
    # cross-model review named as finding fatigue. `no-floor` is the narrower
    # statement and names the same fix first, so it wins the line.
    floored_out = {
        (f.path, f.line) for f in findings if f.kind == "no-floor"
    }
    for name, doms in sorted(enumerated.items()):
        if name in ratcheted:
            continue
        d = doms[0]
        if (d.path, d.line) in floored_out:
            continue
        findings.append(Finding(
            "unratcheted", d.path, d.line, d.test,
            f"enumerates `{name}` live, and nothing pins its membership — a "
            f"member REMOVED from the registry keeps this green, because the "
            f"loop ranges over whatever the registry now holds. Pin a floor "
            f"with `# totality: ratchet — <why>` on a hand-list test",
            registry=name,
        ))

    stats = {
        "source_files": len(src_files),
        "test_files": len(test_files),
        "ratcheted": len(ratcheted),
        "enumerated": len(enumerated),
        "registries": len(registries),
        "domains": domains_seen,
    }
    return findings, stats


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

ORDER = {"ratchet-broken": 0, "sampled-domain": 1, "stale-ack": 2,
         "no-floor": 3, "unratcheted": 4}


def report(findings: list[Finding], stats: dict) -> str:
    out = [
        "",
        "  TOTALITY — a test that enumerates a domain by copying it",
        "",
        f"  {stats['source_files']} source file(s) · {stats['registries']} registry/ies · "
        f"{stats['test_files']} test file(s) · {stats['domains']} iterated domain(s)",
        "",
    ]
    if not findings:
        out += ["  nothing to report.", ""]
        return "\n".join(out)

    for f in sorted(findings, key=lambda f: (ORDER.get(f.kind, 9), f.path, f.line)):
        out.append(f"  [{f.kind}] {f.path}:{f.line}  {f.test}")
        out.append(f"      {f.detail}")
        if f.missing:
            shown = ", ".join(repr(m) for m in f.missing[:8])
            more = "" if len(f.missing) <= 8 else f" … and {len(f.missing) - 8} more"
            out.append(f"      never exercised: {shown}{more}")
        out.append("")

    out += [
        "  Candidates, not defects. A partial domain is often correct — say so on",
        "  the test and it stops being a finding:",
        "",
        "      # totality: partial — <why this subset is the right domain>",
        "",
        "  Otherwise loop the registry itself, and assert a floor so an emptied",
        "  registry cannot pass vacuously.",
        "",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

FIXTURE_SRC = '''
ROTATION_CODES = {"haar": 0, "rht": 1, "none": 2}
SUPPORTED_BITS = (1, 2, 3, 4, 8)
PAIR = {"a": 1, "b": 2}
'''

FIXTURE_TEST = '''
import pytest
from fixture_src import ROTATION_CODES, SUPPORTED_BITS

DIMS = [64, 128, 384, 768, 1024]
LIVE = sorted(ROTATION_CODES)


@pytest.mark.parametrize("rotation", ["haar", "rht"])
def test_copies_the_registry(rotation):
    assert rotation


# totality: partial — mojo has no construction for "none"
@pytest.mark.parametrize("rotation", ["haar", "rht"])
def test_acknowledged_subset(rotation):
    assert rotation


@pytest.mark.parametrize("bits", [1, 2, 3, 4])
def test_copies_the_widths(bits):
    assert bits


@pytest.mark.parametrize("d", DIMS)
def test_local_fixture_is_not_a_copy(d):
    assert d


@pytest.mark.parametrize("rotation", LIVE)
def test_live_without_floor(rotation):
    assert rotation


# totality: partial — stale, this one covers everything
@pytest.mark.parametrize("rotation", sorted(ROTATION_CODES))
def test_stale_ack(rotation):
    assert rotation


def test_pair_is_below_the_registry_floor():
    for k in ["a"]:
        assert k
'''

FIXTURE_TEST_FLOORED = '''
import pytest
from fixture_src import ROTATION_CODES

LIVE = sorted(ROTATION_CODES)


def test_floor():
    assert len(LIVE) >= 3


@pytest.mark.parametrize("rotation", LIVE)
def test_live_with_floor(rotation):
    assert rotation
'''


def selftest() -> int:
    import tempfile

    fails = []

    def check(label, ok, detail=""):
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}" + ("" if ok else f"  -> {detail}"))
        if not ok:
            fails.append(label)

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / "fixture_src.py").write_text(FIXTURE_SRC)
        (root / "tests").mkdir()
        (root / "tests" / "test_fixture.py").write_text(FIXTURE_TEST)
        findings, stats = scan(root)

        by = {}
        for f in findings:
            by.setdefault(f.test, []).append(f.kind)

        check("registries found (2 of 3; PAIR is below MIN_REGISTRY)",
              stats["registries"] == 2, str(stats["registries"]))
        check("a literal subset of a registry is reported",
              "sampled-domain" in by.get("test_copies_the_registry", []), str(by))
        check("the missing member is named",
              any(f.missing == ["none"] for f in findings
                  if f.test == "test_copies_the_registry"),
              str([f.missing for f in findings]))
        check("a second registry is matched independently",
              "sampled-domain" in by.get("test_copies_the_widths", []), str(by))
        check("an acknowledged subset is not a finding",
              "test_acknowledged_subset" not in by, str(by))
        check("a test-local fixture list is not a copy",
              "test_local_fixture_is_not_a_copy" not in by, str(by))
        check("a live domain with no floor is reported",
              "no-floor" in by.get("test_live_without_floor", []), str(by))
        check("an ack on a live domain is reported stale",
              "stale-ack" in by.get("test_stale_ack", []), str(by))
        check("a 1-member loop is below MIN_LITERAL",
              "test_pair_is_below_the_registry_floor" not in by, str(by))

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / "fixture_src.py").write_text(FIXTURE_SRC)
        (root / "tests").mkdir()
        (root / "tests" / "test_floored.py").write_text(FIXTURE_TEST_FLOORED)
        findings, _ = scan(root)
        check("a live domain WITH a floor is silent",
              not [f for f in findings if f.kind == "no-floor"],
              str([f.detail for f in findings]))

    print()
    if fails:
        print(f"{len(fails)} check(s) failed: {fails}")
        return 1
    print("all checks passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default=".", help="repository root")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any finding")
    ap.add_argument("--selftest", action="store_true", help="fixtures, no repo")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    root = pathlib.Path(args.path).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    findings, stats = scan(root)
    if args.json:
        print(json.dumps({
            "stats": stats,
            "findings": [
                {"kind": f.kind, "path": f.path, "line": f.line, "test": f.test,
                 "detail": f.detail, "missing": f.missing, "registry": f.registry}
                for f in findings
            ],
        }, indent=2, default=str))
    else:
        print(report(findings, stats))
    return 1 if (findings and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
