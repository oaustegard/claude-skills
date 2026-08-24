#!/usr/bin/env python3
"""claims.py — the declared invariants of a repository, and what backs them.

`totality_lint.py` answers "is this test's domain complete?". It presumes a
test exists. The harder question is the one coherence's own Known Limits
concedes it does not answer: *nothing enforces `exists ⇒ declared`*. An
invariant the code depends on but no test names is invisible to every gate.

A claim here is a test whose docstring opens with `invariant:`. No new file
format, no new syntax, and the claim inherits its test's pass/fail for free:

    def test_every_declared_rotation_round_trips(rotation):
        '''invariant: every declared rotation survives the on-disk formats.

        refuted: added "hadamard2" to ROTATION_CODES with no construction
        behind it -> the whole suite stayed green at 267 passed while this
        went red on [hadamard2].
        '''

Two lines, two jobs. `invariant:` states what must hold. `refuted:` records
what was broken on purpose and what went red — the observed negative control,
and the only thing separating a claim that holds from a claim that cannot
fail. A green test and an unfalsifiable one are indistinguishable from
outside; the refutation is what tells them apart, and it is worth writing down
because it is cheap to produce once and impossible to reconstruct later.

Findings:

  unrefuted   an invariant with no `refuted:` line. Advisory, and the whole
              point: break the chokepoint, watch it go red by name, restore,
              write down what you saw.

  unanchored  a registry in source with three or more members that no
              invariant names. A candidate for declaration, not a defect —
              most registries do not need one.

  literal     an invariant whose test iterates a copied literal rather than
              the registry. `totality_lint.py` grades this; it is surfaced
              here so one report answers "what do we claim, and does the
              claim mean anything".

    python3 scripts/claims.py <path>            # the report
    python3 scripts/claims.py <path> --json
    python3 scripts/claims.py <path> --strict   # exit 1 if any finding
    python3 scripts/claims.py --selftest        # fixtures, no repo

Python only, same as `totality_lint.py`, whose registry and domain extractors
this reuses rather than reimplementing.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field


def _load_totality_lint():
    """Import the sibling extractor without requiring a package layout."""
    here = pathlib.Path(__file__).resolve().parent / "totality_lint.py"
    spec = importlib.util.spec_from_file_location("totality_lint", here)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: @dataclass resolves annotations through
    # sys.modules[cls.__module__], which is None for a spec-loaded module.
    sys.modules.setdefault("totality_lint", mod)
    spec.loader.exec_module(mod)
    return mod


tl = _load_totality_lint()

INVARIANT_RE = re.compile(r"^\s*invariant:\s*(.+)", re.I)
REFUTED_RE = re.compile(r"^\s*refuted:\s*(.+)", re.I | re.M)


@dataclass
class Claim:
    statement: str
    test: str
    path: str
    line: int
    refuted: str | None = None
    #: Registries this test iterates live, by name. A claim over a domain is
    #: only as good as the domain it loops.
    anchors: list = field(default_factory=list)
    #: Registries this test iterates as a copied literal.
    copies: list = field(default_factory=list)
    #: Registries this test PINS with a deliberate hand-list. A ratchet is the
    #: complement of an enumeration, not a weaker version of it: an enumeration
    #: loops whatever the domain now holds and is blind to it narrowing.
    ratchets: list = field(default_factory=list)


@dataclass
class Finding:
    kind: str
    detail: str
    path: str = ""
    line: int = 0
    test: str = ""


def _docstring_claim(fn: ast.FunctionDef) -> tuple[str, str | None] | None:
    """(statement, refutation) if this test declares an invariant."""
    doc = ast.get_docstring(fn)
    if not doc:
        return None
    first = doc.splitlines()[0] if doc.splitlines() else ""
    m = INVARIANT_RE.match(first)
    if not m:
        return None
    statement = m.group(1).strip().rstrip(".")
    ref = REFUTED_RE.search(doc)
    refutation = None
    if ref:
        # A refutation runs to the end of its paragraph.
        tail = doc[ref.start():]
        para = tail.split("\n\n", 1)[0]
        refutation = " ".join(para.split())
        refutation = REFUTED_RE.sub("", refutation, count=1).strip() or para.strip()
    return (statement, refutation)


def inventory(root: pathlib.Path) -> tuple[list[Claim], list[tl.Registry], dict]:
    src_files, test_files = [], []
    for p in sorted(root.rglob("*.py")):
        if any(part in tl.SKIP_DIRS for part in p.parts):
            continue
        rel = str(p.relative_to(root))
        (test_files if tl._is_test_path(rel) else src_files).append((p, rel))

    registries: list[tl.Registry] = []
    for p, rel in src_files:
        try:
            registries.extend(tl._registries_py(ast.parse(p.read_text(errors="replace")), rel))
        except (SyntaxError, ValueError, OSError):
            continue

    claims: list[Claim] = []
    for p, rel in test_files:
        try:
            src = p.read_text(errors="replace")
            tree = ast.parse(src)
        except (SyntaxError, ValueError, OSError):
            continue

        imports = tl._imported_modules(tree)
        visible = [r for r in registries if tl._reachable(r, rel, imports)]
        by_name = {}
        for r in visible:
            for key in {r.name, r.name.rsplit(".", 1)[-1]}:
                by_name.setdefault(key, r)

        domains = {}
        for d in tl._domains_py(tree, rel, src):
            domains.setdefault(d.test, []).append(d)

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decl = _docstring_claim(fn)
            if decl is None:
                continue
            statement, refutation = decl
            anchors, copies, ratchets = [], [], []
            for d in domains.get(fn.name, []):
                if d.ack and d.ack[0] == "ratchet" and d.members is not None:
                    for r in visible:
                        if d.members <= r.members:
                            ratchets.append(r.name)
                    hit = tl._nearest_registry(d, visible)
                    if hit and hit[1]:
                        ratchets.append(hit[0].name)
                    continue
                if d.live:
                    reg = next(
                        (by_name[n] for n in d.lookup_names() if n in by_name),
                        None,
                    )
                    if reg:
                        anchors.append(reg.name)
                elif d.members is not None and len(d.members) >= tl.MIN_LITERAL:
                    reg = tl._best_registry(d.members, visible)
                    if reg:
                        copies.append(reg.name)
            claims.append(Claim(
                statement=statement, test=fn.name, path=rel, line=fn.lineno,
                refuted=refutation, anchors=sorted(set(anchors)),
                copies=sorted(set(copies)), ratchets=sorted(set(ratchets)),
            ))

    stats = {
        "source_files": len(src_files),
        "test_files": len(test_files),
        "registries": len(registries),
        "claims": len(claims),
        "refuted": sum(1 for c in claims if c.refuted),
    }
    return claims, registries, stats


def findings_for(claims: list[Claim], registries: list[tl.Registry]) -> list[Finding]:
    out: list[Finding] = []
    for c in claims:
        if c.copies:
            out.append(Finding(
                "literal",
                f'"{c.statement}" is anchored to a test that iterates a COPY of '
                f'{", ".join("`" + n + "`" for n in c.copies)} — the claim cannot '
                f'see a member added to the registry',
                c.path, c.line, c.test,
            ))
        if not c.refuted:
            out.append(Finding(
                "unrefuted",
                f'"{c.statement}" has never been observed failing — break its '
                f'chokepoint, watch it go red by name, restore, and record '
                f'`refuted: <what was broken> -> <what was seen>`',
                c.path, c.line, c.test,
            ))

    named = set()
    for c in claims:
        named.update(c.anchors)
        named.update(c.copies)
        named.update(c.ratchets)
    for r in registries:
        if r.name in named or r.name.rsplit(".", 1)[-1] in named:
            continue
        out.append(Finding(
            "unanchored",
            f"`{r.name}` ({r.kind}, {len(r.members)} members) is enumerated in "
            f"source and no invariant names it",
            r.path, r.line,
        ))
    return out


ORDER = {"literal": 0, "unrefuted": 1, "unanchored": 2}


def report(claims: list[Claim], findings: list[Finding], stats: dict) -> str:
    out = [
        "",
        "  CLAIMS — what this repository declares must hold",
        "",
        f"  {stats['claims']} invariant(s) declared · {stats['refuted']} with an "
        f"observed refutation · {stats['registries']} registry/ies in source",
        "",
    ]
    if claims:
        for c in sorted(claims, key=lambda c: (c.path, c.line)):
            mark = "✓" if c.refuted else "·"
            out.append(f"  {mark} {c.statement}")
            over = ""
            if c.anchors:
                over = f" over {', '.join(c.anchors)}"
            elif c.ratchets:
                over = f" pinning {', '.join(c.ratchets)}"
            out.append(f"      {c.path}:{c.line}  {c.test}{over}")
        out.append("")

    if not findings:
        out += ["  nothing to report.", ""]
        return "\n".join(out)

    for f in sorted(findings, key=lambda f: (ORDER.get(f.kind, 9), f.path, f.line)):
        where = f"{f.path}:{f.line}" + (f"  {f.test}" if f.test else "")
        out.append(f"  [{f.kind}] {where}")
        out.append(f"      {f.detail}")
        out.append("")

    out += [
        "  Candidates, not defects. Most registries need no invariant; an",
        "  `unanchored` row is a question, not a verdict. An `unrefuted` row is",
        "  the one worth clearing — a claim nobody has watched fail is a claim",
        "  nobody has tested.",
        "",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

FIX_SRC = '''
ROTATION_CODES = {"haar": 0, "rht": 1, "none": 2}
UNWATCHED = {"a": 1, "b": 2, "c": 3}
'''

FIX_TEST = '''
import pytest
from fix_src import ROTATION_CODES


def test_round_trips(rotation="haar"):
    """invariant: every declared rotation survives the on-disk formats.

    refuted: added "hadamard2" with no construction -> suite stayed green,
    this went red on [hadamard2].
    """
    for name in ROTATION_CODES:
        assert name


def test_unrefuted():
    """invariant: the codes are stable across releases."""
    for name in ROTATION_CODES:
        assert name


@pytest.mark.parametrize("r", ["haar", "rht"])
def test_claim_over_a_copy(r):
    """invariant: every rotation is accepted by save_params."""
    assert r


def test_not_a_claim():
    """Ordinary test, no declaration."""
    assert True
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
        (root / "fix_src.py").write_text(FIX_SRC)
        (root / "tests").mkdir()
        (root / "tests" / "test_fix.py").write_text(FIX_TEST)
        claims, regs, stats = inventory(root)
        f = findings_for(claims, regs)
        by_test = {c.test: c for c in claims}
        kinds = {(x.kind, x.test) for x in f}

        check("three declarations found, the plain test excluded",
              stats["claims"] == 3 and "test_not_a_claim" not in by_test,
              str(sorted(by_test)))
        check("the statement is captured without its trailing period",
              by_test["test_round_trips"].statement.endswith("on-disk formats"),
              by_test["test_round_trips"].statement)
        check("a refutation is captured",
              "hadamard2" in (by_test["test_round_trips"].refuted or ""),
              str(by_test["test_round_trips"].refuted))
        check("a refuted claim is not reported unrefuted",
              ("unrefuted", "test_round_trips") not in kinds, str(kinds))
        check("an unrefuted claim is reported",
              ("unrefuted", "test_unrefuted") in kinds, str(kinds))
        check("a claim anchored to a live registry records the anchor",
              by_test["test_round_trips"].anchors == ["ROTATION_CODES"],
              str(by_test["test_round_trips"].anchors))
        check("a claim over a copied literal is reported",
              ("literal", "test_claim_over_a_copy") in kinds, str(kinds))
        check("a registry no invariant names is reported unanchored",
              any(x.kind == "unanchored" and "UNWATCHED" in x.detail for x in f),
              str([x.detail for x in f if x.kind == "unanchored"]))
        check("a registry an invariant does name is not reported unanchored",
              not any(x.kind == "unanchored" and "ROTATION_CODES" in x.detail
                      for x in f),
              str([x.detail for x in f if x.kind == "unanchored"]))

    print()
    if fails:
        print(f"{len(fails)} check(s) failed: {fails}")
        return 1
    print("all checks passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default=".", help="repository root")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any finding")
    ap.add_argument("--selftest", action="store_true", help="fixtures, no repo")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    root = pathlib.Path(args.path).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    claims, registries, stats = inventory(root)
    findings = findings_for(claims, registries)
    if args.json:
        print(json.dumps({
            "stats": stats,
            "claims": [
                {"statement": c.statement, "test": c.test, "path": c.path,
                 "line": c.line, "refuted": c.refuted, "anchors": c.anchors,
                 "copies": c.copies}
                for c in claims
            ],
            "findings": [
                {"kind": f.kind, "detail": f.detail, "path": f.path,
                 "line": f.line, "test": f.test}
                for f in findings
            ],
        }, indent=2, default=str))
    else:
        print(report(claims, findings, stats))
    return 1 if (findings and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
