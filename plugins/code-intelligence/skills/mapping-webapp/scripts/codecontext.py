#!/usr/bin/env python3
"""
codecontext.py — Code context for a page, derived at runtime via tree-sitting.

Replaces the former `_MAP.md` readers. mapping-codebases persisted a symbol
inventory to disk; tree-sitting parses the same ASTs in ~700ms for a 250-file
repo and answers queries in under a millisecond, so the context is derived per
run instead of read from committed artifacts.

Every function degrades to an empty result if tree-sitting is unavailable —
callers should render the placeholder rather than fail the run.
"""

import sys
from pathlib import Path

_TREESIT_CANDIDATES = [
    Path("/mnt/skills/user/tree-sitting/scripts"),
    Path(__file__).resolve().parent.parent.parent / "tree-sitting" / "scripts",
]

_cache = None
_scanned_root = None


def _load_engine():
    """Import tree-sitting's engine module, or None if not installed."""
    for cand in _TREESIT_CANDIDATES:
        if (cand / "engine.py").exists():
            sys.path.insert(0, str(cand))
            import engine

            return engine
    return None


def load_cache(codebase: Path):
    """Scan the codebase once per process and return the populated CodeCache.

    Returns None if tree-sitting is not installed.
    """
    global _cache, _scanned_root
    root = str(Path(codebase).resolve())
    if _cache is not None and _scanned_root == root:
        return _cache

    engine = _load_engine()
    if engine is None:
        return None

    _cache = engine.CodeCache()
    _cache.scan(root)
    _scanned_root = root
    return _cache


def _page_keywords(page_path: str) -> list[str]:
    """Route segments worth matching against file and symbol names."""
    keywords = [
        seg.lower() for seg in page_path.strip("/").split("/") if seg and len(seg) > 1
    ]
    return keywords or ["index", "home", "app", "main", "landing"]


def find_relevant_code_context(codebase: Path, page_path: str) -> str:
    """Return a source-structure excerpt relevant to a page path.

    Matches route segments against file paths and symbol names, then renders
    the owning directories' overviews. Falls back to the root overview.
    """
    cache = load_cache(codebase)
    if cache is None:
        return "(tree-sitting not installed — no code context available)"

    keywords = _page_keywords(page_path)

    hit_dirs = []
    for relpath in cache.files:
        low = relpath.lower()
        names = [s.name.lower() for s in cache.file_symbols(relpath)]
        if any(kw in low or any(kw in n for n in names) for kw in keywords):
            d = str(Path(relpath).parent)
            d = "" if d == "." else d
            if d not in hit_dirs:
                hit_dirs.append(d)

    excerpts = []
    for d in hit_dirs[:10]:
        try:
            overview = cache.dir_overview(d, depth=1)
        except Exception:
            continue
        if overview and overview.strip():
            label = d or "(root)"
            excerpts.append(f"### {label}\n{overview}")

    if not excerpts:
        try:
            root_overview = cache.dir_overview("", depth=1)
        except Exception:
            root_overview = ""
        if root_overview.strip():
            excerpts.append(f"### (root)\n{root_overview}")

    return "\n\n".join(excerpts) if excerpts else "(no relevant code context found)"


def discover_html_files(codebase: Path) -> list[str]:
    """Return repo-relative paths of HTML files, from the scanned file list.

    Replaces regex-scraping HTML references out of a root `_MAP.md`; the scan
    already knows every file it walked.
    """
    cache = load_cache(codebase)
    if cache is None:
        return []
    return [f for f in cache.files if f.lower().endswith((".html", ".htm"))]
