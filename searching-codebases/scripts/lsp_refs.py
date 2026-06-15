"""Binding-resolved reference/definition tier for Python sources.

Bridges searching-codebases to the ``python-lsp`` skill so that
cross-reference queries on ``.py`` files are resolved by pyright's binder
instead of by text matching. The win over the regex tier: a same-named but
unrelated symbol (a shadowed name, an unrelated ``helper`` in another module)
is *excluded*, and ``definition`` follows imports across files — neither of
which ripgrep or tree-sitter can do.

This tier is engaged lazily: only when a true cross-reference / definition /
hover is requested, so pyright's index cost is never paid on ordinary text
searches.

Soft-fallback contract: every path that cannot produce a binding-resolved
answer raises :class:`LspUnavailable` with a one-line reason. The caller
(``search.py``) catches it, emits a one-line degradation note, and falls back
to the existing regex/tree-sitting text path. Causes that trigger fallback:
non-Python target (the symbol has no Python definition), pyright/node absent,
or the python-lsp client being unimportable.

Coordinate seam: tree-sitting / ripgrep positions are 1-based; LSP is 0-based.
Conversion happens at the boundary via ``Position.from_one_based(line, col)``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

# Default directories to skip when collecting Python files / occurrences.
_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".tox", "build", "dist", ".mypy_cache", ".pytest_cache", ".idea",
    ".eggs", "site-packages",
}

# Bound the number of files opened in the language server and the number of
# occurrence positions queried, so a huge repo doesn't make the lazy path hang.
_MAX_OPEN_FILES = 600
_MAX_OCCURRENCES = 40


class LspUnavailable(Exception):
    """Signals the binding-resolved path can't run — caller should fall back.

    The message is a single line suitable for a user-facing degradation note.
    """


@dataclass
class Site:
    """A 1-based position on a symbol token, plus context for display."""
    file: str          # path relative to root
    line: int          # 1-based line
    col: int           # 1-based column of the symbol token
    kind: str = ""     # tree-sitting symbol kind (function/class/method/...)
    line_text: str = ""


# ── locating sibling skills ──────────────────────────────────────────────────

def _skill_scripts(name: str, env_var: Optional[str] = None) -> Optional[str]:
    """Locate a sibling skill's ``scripts/`` dir across deploy and dev layouts.

    Order: explicit env override, the installed ``/mnt/skills/user`` location,
    then a sibling of this repo checkout (``<repo>/<name>/scripts``).
    """
    candidates: List[str] = []
    if env_var and os.environ.get(env_var):
        candidates.append(os.environ[env_var])
    candidates.append(f"/mnt/skills/user/{name}/scripts")
    # parents[0]=scripts, [1]=searching-codebases, [2]=repo root
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(str(repo_root / name / "scripts"))
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return None


def _import_lsp_client():
    """Import the python-lsp client, or raise LspUnavailable on a soft miss."""
    scripts = _skill_scripts("python-lsp", env_var="PYTHON_LSP_SCRIPTS")
    if not scripts:
        raise LspUnavailable("python-lsp skill not found (binding-resolved tier unavailable)")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        import lsp_client  # noqa: F401
        return lsp_client
    except ImportError as e:  # pragma: no cover - import-path dependent
        raise LspUnavailable(f"cannot import python-lsp client: {e}")


def _code_cache(root: str):
    """Build a tree-sitting CodeCache over ``root``, or raise LspUnavailable."""
    scripts = _skill_scripts("tree-sitting", env_var="TREE_SITTING_SCRIPTS")
    if not scripts:
        raise LspUnavailable("tree-sitting skill not found (cannot resolve symbol position)")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from engine import CodeCache
    except ImportError as e:  # pragma: no cover - import-path dependent
        raise LspUnavailable(f"cannot import tree-sitting engine: {e}")
    cache = CodeCache()
    cache.scan(root)
    return cache


# ── symbol → position resolution ─────────────────────────────────────────────

def _col_of(line_text: str, name: str) -> int:
    """1-based column of the first whole-word occurrence of ``name`` in a line.

    Falls back to a substring search, then to column 1, so a position is always
    produced even if the token is adjacent to non-word characters.
    """
    m = re.search(rf"\b{re.escape(name)}\b", line_text)
    if m:
        return m.start() + 1
    idx = line_text.find(name)
    return (idx + 1) if idx >= 0 else 1


def _read_line(root: str, rel: str, line1: int) -> str:
    try:
        with open(os.path.join(root, rel), "r", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return ""
    return lines[line1 - 1].rstrip("\n") if 0 < line1 <= len(lines) else ""


def definition_sites(root: str, symbol: str) -> List[Site]:
    """Definition sites of ``symbol`` in Python files, via tree-sitting.

    Returns one :class:`Site` per ``def`` / ``class`` / method named exactly
    ``symbol`` (children included). Empty when the symbol has no Python
    definition — which is the non-Python / wrong-target fallback signal.
    """
    cache = _code_cache(root)
    sites: List[Site] = []
    for sym in cache.find_symbol(symbol, limit=200):
        if sym.name != symbol:
            continue  # find_symbol does substring matching; we want exact
        if not sym.file.endswith(".py"):
            continue
        text = _read_line(root, sym.file, sym.line)
        sites.append(Site(file=sym.file, line=sym.line, col=_col_of(text, symbol),
                          kind=sym.kind, line_text=text))
    return sites


def _find_ripgrep() -> Optional[str]:
    from shutil import which
    return which("rg")


def occurrence_sites(root: str, symbol: str, limit: int = _MAX_OCCURRENCES) -> List[Site]:
    """Every textual ``\\bsymbol\\b`` occurrence in ``.py`` files under root.

    Used as anchors for ``definition`` (so it can follow an import from any use
    site) and to bound the set of files opened in the language server. Text
    matching here is intentional and safe — it is a *superset* of the real
    references; pyright narrows it to the binding-resolved set.
    """
    rg = _find_ripgrep()
    sites: List[Site] = []
    pattern = rf"\b{re.escape(symbol)}\b"
    if rg:
        cmd = [rg, "--no-heading", "--line-number", "--column", "--color=never",
               "-t", "py"]
        for d in _SKIP_DIRS:
            cmd.extend(["--glob", f"!{d}"])
        cmd.extend(["-e", pattern, root])
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            out = ""
        for line in out.splitlines():
            parts = line.split(":", 3)
            if len(parts) >= 4 and parts[1].isdigit() and parts[2].isdigit():
                rel = os.path.relpath(parts[0], root)
                sites.append(Site(file=rel, line=int(parts[1]), col=int(parts[2]),
                                  line_text=parts[3]))
                if len(sites) >= limit:
                    break
        return sites
    # No ripgrep: fall back to a Python walk.
    rx = re.compile(pattern)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", errors="replace") as f:
                    for i, text in enumerate(f, start=1):
                        m = rx.search(text)
                        if m:
                            sites.append(Site(file=os.path.relpath(fp, root), line=i,
                                              col=m.start() + 1, line_text=text.rstrip("\n")))
                            if len(sites) >= limit:
                                return sites
            except OSError:
                continue
    return sites


# ── the query ────────────────────────────────────────────────────────────────

def lsp_query(root: str, symbol: str, op: str = "references",
              max_open: int = _MAX_OPEN_FILES, verbose: bool = False) -> dict:
    """Run a binding-resolved ``op`` for ``symbol`` over the Python sources.

    ``op`` is one of ``references`` | ``definition`` | ``hover``.

    - ``references``: anchored at each definition site; pyright returns the
      binding-resolved uses, excluding same-named symbols of other bindings.
      Results are grouped per definition (per binding).
    - ``definition``: anchored at each occurrence; follows imports to the real
      definition(s); results are unioned and de-duplicated.
    - ``hover``: anchored at each definition site; returns the inferred
      type/signature string.

    Raises :class:`LspUnavailable` (soft fallback) when the binding-resolved
    answer cannot be produced.
    """
    if op not in ("references", "definition", "hover"):
        raise ValueError(f"unknown op: {op!r}")

    lsp = _import_lsp_client()
    Position = lsp.Position

    defs = definition_sites(root, symbol)
    occurrences = occurrence_sites(root, symbol)
    if not defs and not occurrences:
        raise LspUnavailable(f"no Python occurrence of {symbol!r} found")
    if op in ("references", "hover") and not defs:
        raise LspUnavailable(f"no Python definition of {symbol!r} found")

    # Ensure pyright is available; fail soft (one-line reason) if not.
    try:
        lsp.ensure_pyright(install=True)
    except lsp.BootstrapError as e:
        raise LspUnavailable(str(e).splitlines()[0])

    # Relevant files to open = every file that mentions the symbol, plus the
    # definition files. This builds pyright's model for exactly the files that
    # could contain a reference, without indexing the whole repo.
    open_files: Set[str] = {s.file for s in occurrences} | {s.file for s in defs}
    files = sorted(f for f in open_files if f.endswith(".py"))
    truncated = len(files) > max_open
    if truncated:
        files = files[:max_open]

    note_parts: List[str] = []
    results: List[dict] = []
    try:
        with lsp.LSPClient(root) as client:
            if files:
                client.open_all(*files)
            if not client.wait_for_index(timeout=30):
                note_parts.append("pyright index wait timed out; results may be incomplete")

            if op == "references":
                for d in defs:
                    pos = Position.from_one_based(d.line, d.col)
                    locs = client.references(d.file, pos.line, pos.character)
                    results.append({"anchor": d, "locations": locs})
            elif op == "hover":
                for d in defs:
                    pos = Position.from_one_based(d.line, d.col)
                    results.append({"anchor": d, "hover": client.hover(d.file, pos.line, pos.character)})
            else:  # definition
                anchors = occurrences or defs
                seen = set()
                union = []
                for a in anchors:
                    pos = Position.from_one_based(a.line, a.col)
                    for loc in client.definition(a.file, pos.line, pos.character):
                        key = (loc.path, loc.start_line, loc.start_char)
                        if key not in seen:
                            seen.add(key)
                            union.append(loc)
                results.append({"anchor": None, "locations": union})
    except LspUnavailable:
        raise
    except Exception as e:  # any client/runtime failure → soft fallback
        raise LspUnavailable(f"binding-resolved query failed: {e}")

    if truncated:
        note_parts.append(f"opened first {max_open} of {len(open_files)} candidate files")

    return {
        "op": op,
        "symbol": symbol,
        "results": results,
        "opened": len(files),
        "note": "; ".join(note_parts) or None,
    }


# ── formatting ───────────────────────────────────────────────────────────────

def _rel(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def format_lsp(result: dict, root: str, json_out: bool = False) -> str:
    """Render an :func:`lsp_query` result. LSP 0-based positions become 1-based."""
    if json_out:
        import json
        payload = {"op": result["op"], "symbol": result["symbol"],
                   "opened": result["opened"], "note": result["note"], "results": []}
        for grp in result["results"]:
            entry: dict = {}
            anchor = grp.get("anchor")
            if anchor is not None:
                entry["anchor"] = {"file": anchor.file, "line": anchor.line,
                                   "col": anchor.col, "kind": anchor.kind}
            if "hover" in grp:
                entry["hover"] = grp["hover"]
            if "locations" in grp:
                entry["locations"] = [
                    {"file": _rel(loc.path, root), "line": loc.start_line + 1,
                     "col": loc.start_char + 1} for loc in grp["locations"]
                ]
            payload["results"].append(entry)
        return json.dumps(payload, indent=2)

    op = result["op"]
    sym = result["symbol"]
    lines = [f"{sym} — binding-resolved {op} (python-lsp)"]
    total = 0
    for grp in result["results"]:
        anchor = grp.get("anchor")
        if "hover" in grp:
            where = f"{anchor.file}:{anchor.line}" if anchor else ""
            hover = grp["hover"] or "(no type information)"
            lines.append(f"  {where}  {hover}")
            total += 1
            continue
        locs = grp.get("locations", [])
        if anchor is not None:
            lines.append(f"  definition {anchor.file}:{anchor.line}"
                         f"{f' ({anchor.kind})' if anchor.kind else ''}")
        for loc in locs:
            lines.append(f"    {_rel(loc.path, root)}:{loc.start_line + 1}:{loc.start_char + 1}")
            total += 1
        if anchor is not None and not locs:
            lines.append("    (no references)")
    if op == "references":
        lines.append(f"  {total} reference{'s' if total != 1 else ''} "
                     f"(binding-resolved; same-named symbols of other bindings excluded)")
    if result.get("note"):
        lines.append(f"  note: {result['note']}")
    return "\n".join(lines)
