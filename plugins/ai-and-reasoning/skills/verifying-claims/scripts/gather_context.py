#!/usr/bin/env python3
"""gather_context.py — assemble the inputs for an agent-driven doc/code/test
consistency review.

This does the *deterministic* half of verifying-claims: it extracts, from
source, the things a reviewer needs to judge whether a document's prose still
matches reality — the public API surface and the test inventory — and bundles
them with the document text. It makes no judgments. The semantic comparison
(does the prose agree with the code and the tests?) is the agent's job.

Sources are parsed with `ast`, never imported, so no module top-level code runs.

Usage:
    python3 gather_context.py --doc README.md --src pkg/ --tests tests/
    python3 gather_context.py --doc docs/api.md --src a.py --src b.py
    python3 gather_context.py --doc README.md --src pkg/ --json
"""

import argparse
import ast
import json
import os
import sys


def _iter_py(paths):
    for p in paths:
        if os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = [d for d in dirnames
                               if d not in ("__pycache__", ".git") and not d.startswith(".")]
                for fn in sorted(filenames):
                    if fn.endswith(".py"):
                        yield os.path.join(dirpath, fn)
        elif p.endswith(".py") and os.path.isfile(p):
            yield p


def _sig(node: ast.FunctionDef) -> str:
    a = node.args
    parts = []
    posonly = getattr(a, "posonlyargs", [])
    for arg in posonly:
        parts.append(arg.arg)
    if posonly:
        parts.append("/")
    defaults = list(a.defaults)
    pos = list(a.args)
    n_no_default = len(pos) - len(defaults)
    for i, arg in enumerate(pos):
        parts.append(arg.arg if i < n_no_default else f"{arg.arg}=...")
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    elif a.kwonlyargs:
        parts.append("*")
    for arg, d in zip(a.kwonlyargs, a.kw_defaults):
        parts.append(arg.arg if d is None else f"{arg.arg}=...")
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    return ", ".join(parts)


def _doc1(node) -> str:
    d = ast.get_docstring(node)
    return d.strip().splitlines()[0].strip() if d else ""


def api_surface(src_paths):
    out = []
    for path in _iter_py(src_paths):
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (SyntaxError, UnicodeDecodeError) as e:
            out.append({"file": path, "error": str(e), "defs": []})
            continue
        defs = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                defs.append({"name": node.name, "sig": _sig(node), "doc": _doc1(node)})
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                methods = []
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        not m.name.startswith("_") or m.name == "__init__"
                    ):
                        methods.append({"name": f"{node.name}.{m.name}", "sig": _sig(m), "doc": _doc1(m)})
                defs.append({"name": node.name, "sig": None, "doc": _doc1(node), "methods": methods})
        if defs:
            out.append({"file": path, "defs": defs})
    return out


def test_inventory(test_paths):
    out = []
    for path in _iter_py(test_paths):
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (SyntaxError, UnicodeDecodeError):
            continue
        tests = []

        def scan(body):
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                    n_assert = sum(isinstance(x, ast.Assert) for x in ast.walk(node))
                    tests.append({"name": node.name, "doc": _doc1(node), "asserts": n_assert})
                elif isinstance(node, ast.ClassDef):
                    scan(node.body)

        scan(tree.body)
        if tests:
            out.append({"file": path, "tests": tests})
    return out


def render_md(doc_path, doc_text, api, tests):
    L = [f"# Context bundle for `{doc_path}`", ""]
    L += ["## Document", "", "```markdown", doc_text.rstrip(), "```", ""]
    L += ["## API surface (from source, not imported)", ""]
    if not api:
        L.append("_(no source provided)_")
    for f in api:
        L.append(f"### `{f['file']}`")
        if f.get("error"):
            L.append(f"- parse error: {f['error']}")
            continue
        for d in f["defs"]:
            if d.get("sig") is None and "methods" in d:
                L.append(f"- class `{d['name']}`" + (f" — {d['doc']}" if d["doc"] else ""))
                for m in d["methods"]:
                    L.append(f"    - `{m['name']}({m['sig']})`" + (f" — {m['doc']}" if m["doc"] else ""))
            else:
                L.append(f"- `{d['name']}({d['sig']})`" + (f" — {d['doc']}" if d["doc"] else ""))
        L.append("")
    L += ["## Tests (names + assertion counts, from source)", ""]
    if not tests:
        L.append("_(no tests provided)_")
    for f in tests:
        L.append(f"### `{f['file']}`")
        for t in f["tests"]:
            note = t["doc"] or f"{t['asserts']} assert(s)"
            L.append(f"- `{t['name']}` — {note}")
        L.append("")
    L += ["---", "Reviewer: compare each claim the Document makes against the API surface and the",
          "Tests above. Report drift as PASS / FAIL / UNSUPPORTED (no test backs the claim) /",
          "STALE (claim refers to something that no longer exists). The behavioral gate is the",
          "test suite; this review covers only whether the prose matches reality."]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Bundle doc + API surface + test inventory for review.")
    ap.add_argument("--doc", required=True)
    ap.add_argument("--src", action="append", default=[], help="source file or dir (repeatable)")
    ap.add_argument("--tests", action="append", default=[], help="test file or dir (repeatable)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.doc):
        print(f"doc not found: {args.doc}", file=sys.stderr)
        return 2
    doc_text = open(args.doc, encoding="utf-8").read()
    api = api_surface(args.src)
    tests = test_inventory(args.tests)

    if args.json:
        print(json.dumps({"doc": args.doc, "doc_text": doc_text, "api": api, "tests": tests}, indent=2))
    else:
        print(render_md(args.doc, doc_text, api, tests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
