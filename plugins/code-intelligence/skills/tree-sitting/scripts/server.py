"""
tree-sitting: MCP server for AST-powered code navigation.

Parses codebases with tree-sitter, caches ASTs in memory,
and exposes query tools for fast symbol lookup, navigation,
and source retrieval.

Install: uv pip install fastmcp tree-sitter-language-pack
Run:     fastmcp run server.py
         python server.py                    # stdio
         python server.py --port 8080        # SSE
"""

from typing import Annotated, Optional
from pydantic import Field
from fastmcp import FastMCP
from engine import cache, CodeCache

mcp = FastMCP(
    name="tree-sitting",
    instructions=(
        "AST-powered code navigation. Call `scan` first with a repo path, "
        "then use find_symbol, file_symbols, dir_overview, tree_overview, "
        "get_source, and references to explore the codebase. "
        "All queries run against in-memory parsed ASTs — sub-millisecond."
    ),
)


@mcp.tool(annotations={"title": "Scan Codebase", "destructiveHint": False})
def scan(
    path: Annotated[str, Field(description="Absolute path to codebase root")],
    skip: Annotated[Optional[str], Field(
        description="Comma-separated dirs to skip (default: .git,node_modules,__pycache__,...)",
        default=None
    )] = None,
) -> str:
    """Parse all source files under path into ASTs. Must be called first.
    Fast: ~700ms for a 3MB/250-file repo. Results cached for all subsequent queries."""
    import time
    t0 = time.perf_counter()
    skip_set = set(skip.split(',')) if skip else None
    stats = cache.scan(path, skip=skip_set)
    elapsed = (time.perf_counter() - t0) * 1000
    stats['elapsed_ms'] = round(elapsed)
    return (
        f"Scanned {stats['files']} files ({stats['bytes']//1024} KB) in {stats['elapsed_ms']}ms\n"
        f"Symbols: {stats['symbols']} | Languages: {', '.join(stats['languages'])}\n"
        f"Errors: {stats['errors']}"
    )


@mcp.tool(annotations={"title": "Tree Overview", "readOnlyHint": True})
def tree_overview() -> str:
    """High-level directory tree with file and symbol counts per directory.
    Call after scan. Good first orientation tool."""
    if not cache.is_loaded:
        return "No codebase scanned. Call scan() first."
    return cache.tree_overview()


@mcp.tool(annotations={"title": "Directory Overview", "readOnlyHint": True})
def dir_overview(
    path: Annotated[str, Field(description="Directory path relative to repo root ('' for root)")] = '',
) -> str:
    """List files and their top-level symbols for a specific directory.
    Like a dynamic _MAP.md for one directory."""
    if not cache.is_loaded:
        return "No codebase scanned. Call scan() first."
    return cache.dir_overview(path)


@mcp.tool(annotations={"title": "Find Symbol", "readOnlyHint": True})
def find_symbol(
    query: Annotated[str, Field(description="Symbol name, substring, or wildcard pattern (e.g. 'ts_parser_*')")],
    kind: Annotated[Optional[str], Field(
        description="Filter by kind: function, class, struct, enum, method, const, define, type",
        default=None
    )] = None,
    limit: Annotated[int, Field(description="Max results", default=20)] = 20,
) -> str:
    """Search for symbols across the entire codebase by name.
    Supports exact match, substring, and glob patterns."""
    if not cache.is_loaded:
        return "No codebase scanned. Call scan() first."
    results = cache.find_symbol(query, kind=kind, limit=limit)
    if not results:
        return f"No symbols matching '{query}'"
    lines = [f"Found {len(results)} symbol(s) matching '{query}':\n"]
    for sym in results:
        lines.append(f"  {sym.file}:{sym.line} — {sym.format_oneline()}")
    return '\n'.join(lines)


@mcp.tool(annotations={"title": "File Symbols", "readOnlyHint": True})
def file_symbols(
    path: Annotated[str, Field(description="File path relative to repo root (or partial match)")],
) -> str:
    """List all symbols in a specific file with signatures and doc comments.
    The equivalent of reading a _MAP.md entry for one file."""
    if not cache.is_loaded:
        return "No codebase scanned. Call scan() first."
    syms = cache.file_symbols(path)
    if not syms:
        return f"No symbols found for '{path}'"
    imps = cache.file_imports(path)
    lines = []
    if imps:
        preview = ', '.join(imps[:6])
        if len(imps) > 6:
            preview += f', ... +{len(imps)-6}'
        lines.append(f"Imports: {preview}\n")
    for sym in syms:
        lines.append(sym.format_oneline())
        for child in sym.children:
            lines.append(f"  {child.format_oneline()}")
    return '\n'.join(lines)


@mcp.tool(annotations={"title": "Get Source", "readOnlyHint": True})
def get_source(
    symbol: Annotated[str, Field(description="Symbol name to get source for")],
    file: Annotated[Optional[str], Field(
        description="File path to disambiguate if symbol exists in multiple files",
        default=None
    )] = None,
) -> str:
    """Get the source code of a specific symbol (function, class, struct).
    Finds the symbol, then returns its source lines."""
    if not cache.is_loaded:
        return "No codebase scanned. Call scan() first."
    results = cache.find_symbol(symbol, limit=5)
    if file:
        results = [s for s in results if file in s.file]
    if not results:
        return f"Symbol '{symbol}' not found"
    # Prefer implementation (largest span) over declaration
    sym = max(results, key=lambda s: s.end_line - s.line)
    header = f"# {sym.name} ({sym.kind}) in {sym.file}:{sym.line}-{sym.end_line}"
    if sym.doc:
        header += f"\n# {sym.doc}"
    source = cache.get_source_range(sym.file, sym.line, sym.end_line)
    return f"{header}\n\n{source}"


@mcp.tool(annotations={"title": "References", "readOnlyHint": True})
def references(
    symbol: Annotated[str, Field(description="Symbol name to find references for")],
    limit: Annotated[int, Field(description="Max results", default=20)] = 20,
) -> str:
    """Find all textual references to a symbol across the codebase.
    Fast grep-like search against cached source."""
    if not cache.is_loaded:
        return "No codebase scanned. Call scan() first."
    refs = cache.references(symbol, limit=limit)
    if not refs:
        return f"No references to '{symbol}'"
    lines = [f"Found {len(refs)} reference(s) to '{symbol}':\n"]
    for ref in refs:
        lines.append(f"  {ref['file']}:{ref['line']} | {ref['text']}")
    return '\n'.join(lines)


if __name__ == "__main__":
    import sys
    if '--port' in sys.argv:
        idx = sys.argv.index('--port')
        port = int(sys.argv[idx + 1])
        mcp.run(transport='sse', port=port)
    else:
        mcp.run()
