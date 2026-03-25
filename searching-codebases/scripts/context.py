"""
Expand search match lines into full structural context (functions/classes).

Uses _MAP.md files (from mapping-codebases) when available, with optional
tree-sitter fallback. Returns the complete function or class containing
a match, not just the matching line.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


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


@dataclass
class MapSymbol:
    """A symbol parsed from a _MAP.md file."""
    name: str
    kind: str  # C=class, f=function, m=method
    line: int
    signature: str = ""
    parent: Optional[str] = None


# Extension → language mapping
EXT_TO_LANG = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript",
    ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".java": "java", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".hpp": "cpp", ".cc": "cpp",
    ".cs": "csharp", ".php": "php",
}

_KIND_TO_NODE_TYPE = {"C": "class", "f": "function", "m": "method"}


def parse_map_file(map_path: str) -> Dict[str, List[MapSymbol]]:
    """Parse a _MAP.md file into symbols grouped by filename."""
    symbols_by_file: Dict[str, List[MapSymbol]] = {}
    current_file = None
    current_class = None

    with open(map_path, "r") as f:
        for line in f:
            # File header: ### filename.py
            file_match = re.match(r"^###\s+(.+)$", line)
            if file_match:
                current_file = file_match.group(1).strip()
                current_class = None
                if current_file not in symbols_by_file:
                    symbols_by_file[current_file] = []
                continue

            if not current_file:
                continue

            # Symbol: - **Name** (C/f/m) `signature` :line
            sym_match = re.match(
                r"^(\s*)-\s+\*\*(\w+)\*\*\s+\((\w)\)\s*(?:`([^`]*)`\s*)?:(\d+)",
                line,
            )
            if sym_match:
                indent = len(sym_match.group(1))
                name = sym_match.group(2)
                kind = sym_match.group(3)
                sig = sym_match.group(4) or ""
                line_num = int(sym_match.group(5))

                parent = None
                if indent >= 2 and current_class:
                    parent = current_class

                if kind == "C":
                    current_class = name

                symbols_by_file[current_file].append(
                    MapSymbol(name=name, kind=kind, line=line_num,
                              signature=sig, parent=parent)
                )

    return symbols_by_file


def find_map_for_file(file_path: str, search_root: str) -> Optional[str]:
    """Find the _MAP.md that covers a given file."""
    directory = os.path.dirname(file_path)
    while directory.startswith(search_root):
        candidate = os.path.join(directory, "_MAP.md")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return None


def expand_match(file_path: str, line_number: int, search_root: str,
                 signatures_only: bool = True) -> Optional[CodeContext]:
    """
    Expand a match at file:line into its containing function/class.

    Uses _MAP.md data for structural boundaries. Falls back to returning
    a context window around the match if no map is available.

    Args:
        file_path: Absolute path to matched file
        line_number: 1-indexed line number of the match
        search_root: Root directory (for finding _MAP.md files)
        signatures_only: Return only signature, not full body
    """
    map_path = find_map_for_file(file_path, search_root)
    if map_path:
        return _expand_from_map(file_path, line_number, map_path, signatures_only)
    return _expand_window(file_path, line_number)


def _expand_from_map(file_path: str, line_number: int, map_path: str,
                     signatures_only: bool) -> Optional[CodeContext]:
    """Expand using structural data from _MAP.md."""
    filename = os.path.basename(file_path)
    lang = EXT_TO_LANG.get(os.path.splitext(file_path)[1].lower())

    symbols_by_file = parse_map_file(map_path)
    symbols = symbols_by_file.get(filename, [])
    if not symbols:
        return _expand_window(file_path, line_number)

    # Find containing symbol (last symbol with line <= match)
    containing = None
    for sym in symbols:
        if sym.line <= line_number:
            containing = sym
        else:
            break

    if not containing:
        return _expand_window(file_path, line_number)

    # Find end: next non-child symbol's line - 1
    sym_idx = symbols.index(containing)
    next_line = None
    for i in range(sym_idx + 1, len(symbols)):
        if containing.kind == "C" and symbols[i].parent == containing.name:
            continue
        next_line = symbols[i].line
        break

    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
    except (FileNotFoundError, PermissionError):
        return None

    start_line = containing.line
    end_line = (next_line - 1) if next_line else len(lines)

    # Trim trailing blanks
    while end_line > start_line and not lines[end_line - 1].strip():
        end_line -= 1

    source = "".join(lines[start_line - 1 : end_line])

    signature = None
    if signatures_only:
        sig = containing.signature or ""
        if lang == "python":
            if containing.kind == "C":
                signature = f"class {containing.name}:\n    ..."
            else:
                signature = f"def {containing.name}{sig}:\n    ..."
        elif lang in ("javascript", "typescript"):
            if containing.kind == "C":
                signature = f"class {containing.name} {{ ... }}"
            else:
                signature = f"function {containing.name}{sig} {{ ... }}"
        elif lang == "go":
            signature = f"func {containing.name}{sig} {{ ... }}"
        else:
            signature = f"{containing.name}{sig}"

    display = f"{containing.parent}.{containing.name}" if containing.parent else containing.name
    node_type = _KIND_TO_NODE_TYPE.get(containing.kind, containing.kind)

    return CodeContext(
        file_path=file_path, start_line=start_line, end_line=end_line,
        match_line=line_number, node_type=node_type, name=display,
        source=source, language=lang, signature=signature,
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
    source = "".join(lines[start - 1 : end])
    lang = EXT_TO_LANG.get(os.path.splitext(file_path)[1].lower())

    return CodeContext(
        file_path=file_path, start_line=start, end_line=end,
        match_line=line_number, node_type="context", name="",
        source=source, language=lang,
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
