"""
Expand search match lines into full structural context (functions/classes).

Uses tree-sitting's AST cache for symbol boundaries. Scans the repo once
on first expand call (~700ms), then all expansions are sub-millisecond.
Falls back to a fixed-size context window if tree-sitting is unavailable.
"""

import os
import sys
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CodeContext:
    """A structural code unit containing a match."""
    file_path: str
    start_line: int
    end_line: int
    match_line: int
    node_type: str  # "function", "class", "method"
    name: str
    source: str
    language: Optional[str] = None
    signature: Optional[str] = None


# Lazily initialized tree-sitting cache
_cache = None
_cache_root = None


def _ensure_cache(search_root: str):
    """Scan the repo with tree-sitting on first call. No-op on subsequent calls."""
    global _cache, _cache_root
    if _cache is not None and _cache_root == search_root:
        return _cache

    try:
        ts_scripts = "/mnt/skills/user/tree-sitting/scripts"
        if ts_scripts not in sys.path:
            sys.path.insert(0, ts_scripts)
        from engine import CodeCache

        _cache = CodeCache()
        _cache.scan(search_root)
        _cache_root = search_root
        return _cache
    except Exception as e:
        print(f"tree-sitting unavailable ({e}), using window fallback",
              file=sys.stderr)
        return None


def expand_match(file_path: str, line_number: int, search_root: str,
                 signatures_only: bool = True) -> Optional[CodeContext]:
    """
    Expand a match at file:line into its containing function/class.

    Uses tree-sitting AST data for structural boundaries. Falls back to
    a context window around the match if tree-sitting is unavailable.

    Args:
        file_path: Absolute path to matched file
        line_number: 1-indexed line number of the match
        search_root: Root directory of the codebase
        signatures_only: Return only signature, not full body
    """
    cache = _ensure_cache(search_root)
    if cache is not None:
        return _expand_from_ast(file_path, line_number, search_root,
                                cache, signatures_only)
    return _expand_window(file_path, line_number)


def _expand_from_ast(file_path: str, line_number: int, search_root: str,
                     cache, signatures_only: bool) -> Optional[CodeContext]:
    """Expand using tree-sitting's parsed AST symbols."""
    relpath = os.path.relpath(file_path, search_root)

    # Get symbols for this file from the cache
    entry = cache.files.get(relpath)
    if not entry or not entry.symbols:
        return _expand_window(file_path, line_number)

    # Find the innermost symbol containing this line
    containing = None
    for sym in entry.symbols:
        start = sym.get("start_line") or sym.get("line", 0)
        end = sym.get("end_line", start)
        if start <= line_number <= end:
            # Prefer the most specific (innermost) match
            if containing is None:
                containing = sym
            else:
                prev_start = containing.get("start_line") or containing.get("line", 0)
                if start >= prev_start:
                    containing = sym

    if not containing:
        # No containing symbol — try nearest preceding symbol
        best = None
        for sym in entry.symbols:
            start = sym.get("start_line") or sym.get("line", 0)
            if start <= line_number:
                if best is None or start > (best.get("start_line") or best.get("line", 0)):
                    best = sym
        containing = best

    if not containing:
        return _expand_window(file_path, line_number)

    start_line = containing.get("start_line") or containing.get("line", 1)
    end_line = containing.get("end_line") or start_line

    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
    except (FileNotFoundError, PermissionError):
        return None

    # Ensure end_line doesn't exceed file
    end_line = min(end_line, len(lines))

    # Trim trailing blanks
    while end_line > start_line and not lines[end_line - 1].strip():
        end_line -= 1

    source = "".join(lines[start_line - 1:end_line])

    name = containing.get("name", "")
    kind = containing.get("kind", "function")
    # Normalize kind to node_type
    kind_map = {
        "class": "class", "struct": "class", "interface": "class",
        "enum": "class", "trait": "class",
        "method": "method", "impl_method": "method",
        "function": "function", "func": "function",
    }
    node_type = kind_map.get(kind, kind)

    signature = None
    if signatures_only:
        sig = containing.get("signature", "")
        if sig:
            signature = sig
        else:
            # Use first line as signature fallback
            first_line = lines[start_line - 1].rstrip() if start_line <= len(lines) else name
            signature = first_line

    parent = containing.get("parent")
    display = f"{parent}.{name}" if parent else name

    return CodeContext(
        file_path=file_path, start_line=start_line, end_line=end_line,
        match_line=line_number, node_type=node_type, name=display,
        source=source, language=entry.lang, signature=signature,
    )


def _expand_window(file_path: str, line_number: int,
                   context: int = 10) -> Optional[CodeContext]:
    """Fallback: return a fixed window around the match."""
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
    except (FileNotFoundError, PermissionError):
        return None

    start = max(1, line_number - context)
    end = min(len(lines), line_number + context)
    source = "".join(lines[start - 1:end])

    ext = os.path.splitext(file_path)[1].lower()
    ext_to_lang = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".go": "go", ".rs": "rust", ".rb": "ruby", ".java": "java",
        ".c": "c", ".cpp": "cpp", ".cs": "csharp",
    }

    return CodeContext(
        file_path=file_path, start_line=start, end_line=end,
        match_line=line_number, node_type="context", name="",
        source=source, language=ext_to_lang.get(ext),
    )


def deduplicate_contexts(contexts: List[CodeContext]) -> List[CodeContext]:
    """Remove duplicate expansions (same function from multiple match lines)."""
    seen = set()
    unique = []
    for ctx in contexts:
        key = (ctx.file_path, ctx.start_line, ctx.end_line)
        if key not in seen:
            seen.add(key)
            unique.append(ctx)
    return unique
