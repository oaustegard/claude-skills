#!/usr/bin/env python3
"""
treesit.py — AST-powered code navigation CLI.

Auto-scans on every invocation (~700ms), then runs queries.
Designed for environments where each call is a separate process.

Always prints a tree overview first (progressive disclosure context),
then any query results.

Usage:
    treesit.py REPO [OPTIONS] [QUERIES...]

Options:
    --depth N        Directory depth: -1=all, 0=root only, 1=one level (default: 1)
    --detail LEVEL   Node detail: sparse|normal|full (default: normal)
    --path DIR       Scope to subdirectory (relative to repo root)
    --skip DIRS      Comma-separated dirs to skip (added to defaults)
    --no-tree        Suppress tree overview, show only query results
    --stats          Show scan statistics

Queries:
    find:PATTERN[:KIND[:LIMIT]]    Search symbols by name/glob
    symbols:FILE_PATH              All symbols in a file
    source:SYMBOL[:FILE]           Source code of a symbol
    refs:SYMBOL[:LIMIT]            Find references across codebase
    imports:FILE_PATH              Imports for a file
    dir:DIR_PATH                   Directory overview

No queries = tree overview only.

Detail levels (tree overview rows show per-file symbol lists with line ranges):
    sparse  — name:start-end                         [featuring: complete shape]
    normal  — name(kind_initial):start-end            [exploring: orientation]
    full    — per-symbol formatter + children + imports [exploring: deep dive]
"""

import sys
import os
import argparse
import time


def find_engine():
    """Locate tree-sitting engine."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.'),
        '/mnt/skills/user/tree-sitting/scripts',
    ]
    for p in candidates:
        if os.path.exists(os.path.join(p, 'engine.py')):
            if p not in sys.path:
                sys.path.insert(0, p)
            return p
    return None


def format_symbol_sparse(sym, indent=''):
    """name (kind) :line-end"""
    return f"{indent}{sym.name} ({sym.kind}) :{sym.line}-{sym.end_line}"


def format_symbol_normal(sym, indent=''):
    """name (kind) signature :line-end — doc"""
    parts = [f"{indent}{sym.name} ({sym.kind})"]
    if sym.signature:
        parts.append(f"{sym.signature}")
    parts.append(f":{sym.line}-{sym.end_line}")
    if sym.doc:
        parts.append(f"— {sym.doc}")
    return ' '.join(parts)


def format_symbol_full(sym, indent=''):
    """Normal + children."""
    lines = [format_symbol_normal(sym, indent)]
    for child in sym.children:
        lines.append(format_symbol_normal(child, indent + '  '))
    return '\n'.join(lines)


FORMATTERS = {
    'sparse': format_symbol_sparse,
    'normal': format_symbol_normal,
    'full': format_symbol_full,
}


def tree_overview(cache, depth, detail, scope_path=''):
    """Progressive-disclosure tree overview with depth/detail control."""
    if not cache.root:
        return "No codebase scanned."

    fmt = FORMATTERS[detail]

    # Collect directory stats
    dir_entries = {}  # dirpath -> {files: [...], subdirs: set()}
    for relpath, entry in sorted(cache.files.items()):
        # Apply scope filter
        if scope_path:
            if not relpath.startswith(scope_path.rstrip('/') + '/') and relpath != scope_path:
                continue

        # Compute directory relative to scope
        if scope_path:
            rest = relpath[len(scope_path.rstrip('/')) + 1:]
        else:
            rest = relpath

        parts = rest.split('/')
        dirpart = '/'.join(parts[:-1]) if len(parts) > 1 else ''

        if dirpart not in dir_entries:
            dir_entries[dirpart] = {'files': [], 'subdirs': set()}
        dir_entries[dirpart]['files'].append(entry)

        # Register parent dirs
        for i in range(1, len(parts) - 1):
            parent = '/'.join(parts[:i])
            child_dir = parts[i]
            if parent not in dir_entries:
                dir_entries[parent] = {'files': [], 'subdirs': set()}
            dir_entries[parent]['subdirs'].add(child_dir)

        # Root-level subdirs
        if len(parts) > 1:
            if '' not in dir_entries:
                dir_entries[''] = {'files': [], 'subdirs': set()}
            dir_entries['']['subdirs'].add(parts[0])

    if not dir_entries:
        return f"No files found under '{scope_path}'" if scope_path else "No files scanned."

    lines = []
    display_root = scope_path or (cache.root.name if cache.root else '.')
    total_files = sum(len(d['files']) for d in dir_entries.values())
    total_symbols = sum(
        len(e.symbols) for d in dir_entries.values() for e in d['files']
    )
    lines.append(f"# {display_root}/ ({total_files} files, {total_symbols} symbols)\n")

    def render_dir(dirpath, current_depth):
        info = dir_entries.get(dirpath, {'files': [], 'subdirs': set()})
        dir_indent = '  ' * current_depth

        # Show files at this level
        if detail == 'full':
            for entry in info['files']:
                fname = os.path.basename(entry.path)
                lines.append(f"{dir_indent}  {fname}")
                if entry.imports:
                    preview = ', '.join(entry.imports[:6])
                    if len(entry.imports) > 6:
                        preview += f' +{len(entry.imports) - 6}'
                    lines.append(f"{dir_indent}    imports: {preview}")
                for sym in entry.symbols:
                    lines.append(fmt(sym, dir_indent + '    '))
        elif detail == 'normal':
            for entry in info['files']:
                fname = os.path.basename(entry.path)
                sym_summary = ', '.join(
                    f"{s.name}({s.kind[0]}):{s.line}-{s.end_line}" for s in entry.symbols[:6]
                )
                if len(entry.symbols) > 6:
                    sym_summary += f' +{len(entry.symbols) - 6}'
                lines.append(f"{dir_indent}  {fname}: {sym_summary}" if sym_summary else f"{dir_indent}  {fname}")
        else:  # sparse
            for entry in info['files']:
                fname = os.path.basename(entry.path)
                sym_names = ', '.join(f"{s.name}:{s.line}-{s.end_line}" for s in entry.symbols[:8])
                if len(entry.symbols) > 8:
                    sym_names += f' +{len(entry.symbols) - 8}'
                lines.append(f"{dir_indent}  {fname}: {sym_names}" if sym_names else f"{dir_indent}  {fname}")

        # Show subdirs (respecting depth)
        if depth == -1 or current_depth < depth:
            for subdir in sorted(info['subdirs']):
                child_path = f"{dirpath}/{subdir}" if dirpath else subdir
                child_info = dir_entries.get(child_path, {'files': [], 'subdirs': set()})

                # Count total files recursively under this subdir
                prefix = child_path + '/'
                file_count = sum(
                    len(d['files']) for dp, d in dir_entries.items()
                    if dp == child_path or dp.startswith(prefix)
                )
                sym_count = sum(
                    len(e.symbols)
                    for dp, d in dir_entries.items()
                    if dp == child_path or dp.startswith(prefix)
                    for e in d['files']
                )
                langs = set()
                for dp, d in dir_entries.items():
                    if dp == child_path or dp.startswith(prefix):
                        for e in d['files']:
                            langs.add(e.lang)

                lang_str = ','.join(sorted(langs))
                lines.append(f"{dir_indent}{subdir}/ — {file_count} files, {sym_count} symbols [{lang_str}]")
                render_dir(child_path, current_depth + 1)
        else:
            # At depth limit — show collapsed subdirs
            for subdir in sorted(info['subdirs']):
                child_path = f"{dirpath}/{subdir}" if dirpath else subdir
                prefix = child_path + '/'
                file_count = sum(
                    len(d['files']) for dp, d in dir_entries.items()
                    if dp == child_path or dp.startswith(prefix)
                )
                sym_count = sum(
                    len(e.symbols)
                    for dp, d in dir_entries.items()
                    if dp == child_path or dp.startswith(prefix)
                    for e in d['files']
                )
                lines.append(f"{dir_indent}{subdir}/ — {file_count} files, {sym_count} symbols [...]")

    render_dir('', 0)
    return '\n'.join(lines)


def run_query(cache, query_str, detail='normal'):
    """Parse and execute a query string."""
    fmt = FORMATTERS[detail]

    if ':' in query_str:
        cmd, _, args = query_str.partition(':')
    else:
        return f"Unknown query format: {query_str}\nExpected: find:PATTERN, symbols:FILE, source:SYMBOL, refs:SYMBOL, imports:FILE, dir:PATH"

    cmd = cmd.strip().lower()
    args = args.strip()

    if cmd == 'find':
        # find:PATTERN[:KIND[:LIMIT]]
        parts = args.split(':')
        pattern = parts[0]
        kind = parts[1] if len(parts) > 1 and parts[1] else None
        limit = int(parts[2]) if len(parts) > 2 else 20
        results = cache.find_symbol(pattern, kind=kind, limit=limit)
        if not results:
            return f"No symbols matching '{pattern}'"
        lines = [f"Found {len(results)} symbol(s) matching '{pattern}':\n"]
        for sym in results:
            lines.append(f"  {sym.file}:{fmt(sym)}")
        return '\n'.join(lines)

    elif cmd == 'symbols':
        syms = cache.file_symbols(args)
        if not syms:
            return f"No symbols found for '{args}'"
        lines = [f"Symbols in {args}:\n"]
        for sym in syms:
            lines.append(fmt(sym, '  '))
            if detail == 'full':
                for child in sym.children:
                    lines.append(fmt(child, '    '))
        return '\n'.join(lines)

    elif cmd == 'source':
        # source:SYMBOL[:FILE]
        parts = args.split(':', 1)
        symbol_name = parts[0]
        file_filter = parts[1] if len(parts) > 1 else None
        results = cache.find_symbol(symbol_name, limit=5)
        if file_filter:
            results = [s for s in results if file_filter in s.file]
        if not results:
            return f"Symbol '{symbol_name}' not found"
        sym = max(results, key=lambda s: s.end_line - s.line)
        header = f"# {sym.name} ({sym.kind}) in {sym.file}:{sym.line}-{sym.end_line}"
        if sym.doc:
            header += f"\n# {sym.doc}"
        source = cache.get_source_range(sym.file, sym.line, sym.end_line)
        return f"{header}\n\n{source}"

    elif cmd == 'refs':
        # refs:SYMBOL[:LIMIT]
        parts = args.split(':', 1)
        symbol_name = parts[0]
        limit = int(parts[1]) if len(parts) > 1 else 20
        refs = cache.references(symbol_name, limit=limit)
        if not refs:
            return f"No references to '{symbol_name}'"
        lines = [f"Found {len(refs)} reference(s) to '{symbol_name}':\n"]
        for ref in refs:
            lines.append(f"  {ref['file']}:{ref['line']} | {ref['text']}")
        return '\n'.join(lines)

    elif cmd == 'imports':
        imps = cache.file_imports(args)
        if not imps:
            return f"No imports found for '{args}'"
        return f"Imports in {args}:\n  " + '\n  '.join(imps)

    elif cmd == 'dir':
        return cache.dir_overview(args)

    else:
        return f"Unknown command: {cmd}\nAvailable: find, symbols, source, refs, imports, dir"


def main():
    parser = argparse.ArgumentParser(
        description='AST-powered code navigation. Auto-scans, then queries.',
        epilog='Queries: find:PATTERN symbols:FILE source:SYMBOL refs:SYMBOL imports:FILE dir:PATH'
    )
    parser.add_argument('repo', help='Path to codebase root')
    parser.add_argument('queries', nargs='*', help='Queries to run after scan')
    parser.add_argument('--depth', type=int, default=1,
                        help='Directory depth: -1=all, 0=root, 1=one level (default: 1)')
    parser.add_argument('--detail', choices=['sparse', 'normal', 'full'], default='normal',
                        help='Node detail level (default: normal)')
    parser.add_argument('--path', default='',
                        help='Scope to subdirectory (relative to repo root)')
    parser.add_argument('--skip', default='',
                        help='Comma-separated dirs to skip (added to defaults)')
    parser.add_argument('--no-tree', action='store_true',
                        help='Suppress tree overview, show only query results')
    parser.add_argument('--stats', action='store_true',
                        help='Show scan statistics')

    args, extra = parser.parse_known_args()
    # Extra args are queries (argparse struggles with nargs='*' after options)
    args.queries = list(args.queries) + extra

    # Find and import engine
    engine_path = find_engine()
    if not engine_path:
        print("ERROR: tree-sitting engine not found.", file=sys.stderr)
        sys.exit(1)

    from engine import CodeCache

    # Scan
    cache = CodeCache()
    skip = set(args.skip.split(',')) if args.skip else None
    t0 = time.perf_counter()
    stats = cache.scan(args.repo, skip=skip)
    elapsed = (time.perf_counter() - t0) * 1000

    if args.stats:
        print(f"Scanned {stats['files']} files ({stats['bytes']//1024} KB) in {elapsed:.0f}ms")
        print(f"Symbols: {stats['symbols']} | Languages: {', '.join(stats['languages'])}")
        if stats['errors']:
            print(f"Errors: {stats['errors']}")
        print()

    # Tree overview (unless suppressed)
    if not args.no_tree:
        print(tree_overview(cache, args.depth, args.detail, args.path))

    # Run queries
    for q in args.queries:
        print(f"\n{'─' * 60}")
        print(run_query(cache, q, args.detail))


if __name__ == '__main__':
    main()
