#!/usr/bin/env python3
"""
gather.py — Collect structural data from a codebase via tree-sitting for feature synthesis.

Scans a codebase with tree-sitting's engine, then outputs a structured summary
optimized for LLM consumption: entry points, public APIs, symbol clusters by
directory, and selective source excerpts for key files.

Usage:
    python gather.py /path/to/repo [--skip tests,.github] [--depth 2] [--source-budget 8000]

Output: structured markdown to stdout, suitable as LLM prompt input.
"""

import sys
import os
import argparse
from pathlib import Path

def _find_treesit_engine():
    """Locate tree-sitting engine across known skill directories."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / 'tree-sitting' / 'scripts',  # sibling skill
        Path('/mnt/skills/user/tree-sitting/scripts'),  # Claude.ai skill mount
        Path('/mnt/skills/public/tree-sitting/scripts'),
    ]
    for p in candidates:
        if (p / 'engine.py').exists():
            return p
    return None


def setup_engine():
    """Import tree-sitting engine."""
    engine_path = _find_treesit_engine()
    if engine_path is None:
        print("ERROR: tree-sitting skill not found. Install it first.", file=sys.stderr)
        sys.exit(1)
    sys.path.insert(0, str(engine_path))
    try:
        from engine import CodeCache
        return CodeCache()
    except ImportError as e:
        print(f"ERROR: tree-sitting engine import failed: {e}\n"
              "Install deps: uv pip install tree-sitter-language-pack", file=sys.stderr)
        sys.exit(1)


def classify_symbols(cache) -> dict:
    """Classify symbols into feature-relevant categories."""
    categories = {
        'entry_points': [],    # main, cli, serve, run, app
        'public_api': [],      # exported functions/classes (non-private, non-test)
        'types': [],           # classes, structs, enums, interfaces
        'constants': [],       # defines, const, config
        'tests': [],           # test functions
        'internal': [],        # private/helper functions
    }

    entry_patterns = {'main', 'cli', 'run', 'serve', 'start', 'app', 'init', 'setup', 'boot'}
    test_patterns = {'test_', 'test', 'spec_', 'it_'}

    for relpath, entry in cache.files.items():
        # Skip markdown files — headings aren't code symbols
        if entry.lang == 'markdown':
            continue
        is_test_file = any(p in relpath.lower() for p in ('test', 'spec', '__tests__'))
        for sym in entry.symbols:
            name_lower = sym.name.lower()

            if is_test_file or any(name_lower.startswith(p) for p in test_patterns):
                categories['tests'].append(sym)
            elif name_lower in entry_patterns or (name_lower == '__main__'):
                categories['entry_points'].append(sym)
            elif sym.kind in ('class', 'struct', 'enum', 'interface', 'trait', 'type'):
                categories['types'].append(sym)
            elif sym.kind in ('constant', 'define', 'static'):
                categories['constants'].append(sym)
            elif sym.name.startswith('_'):
                categories['internal'].append(sym)
            else:
                categories['public_api'].append(sym)

    return categories


def identify_key_files(cache, source_budget: int) -> list:
    """Pick files worth reading source from, within a token budget.

    Heuristic: files with the most public symbols, entry points, or
    complex type hierarchies are most likely to reveal feature intent.
    """
    file_scores = []
    for relpath, entry in cache.files.items():
        if any(p in relpath.lower() for p in ('test', 'spec', '__tests__', 'vendor', 'node_modules')):
            continue
        if entry.lang in ('json', 'yaml', 'toml', 'css', 'html', 'markdown'):
            continue

        # Score by: public symbols, entry points, type definitions, children count
        score = 0
        for sym in entry.symbols:
            name_lower = sym.name.lower()
            if name_lower in ('main', 'cli', 'run', 'serve', 'boot', 'app'):
                score += 5
            elif sym.kind in ('class', 'struct', 'trait', 'interface'):
                score += 3 + len(sym.children)
            elif not sym.name.startswith('_'):
                score += 1

        if score > 0:
            source_len = len(entry.source)
            file_scores.append((relpath, score, source_len))

    # Sort by score descending, take files within budget
    file_scores.sort(key=lambda x: x[1], reverse=True)
    selected = []
    remaining = source_budget
    for relpath, score, size in file_scores:
        char_estimate = size  # bytes ≈ chars for source code
        if char_estimate <= remaining:
            selected.append(relpath)
            remaining -= char_estimate
        elif remaining > 2000:
            # Take a partial (first N lines)
            selected.append(relpath)
            break
    return selected


def format_symbol_brief(sym, indent=0) -> str:
    """One-line symbol summary."""
    prefix = '  ' * indent
    parts = [f"{prefix}- **{sym.name}** ({sym.kind})"]
    if sym.signature:
        parts.append(f"`{sym.signature}`")
    parts.append(f"@ {sym.file}:{sym.line}")
    if sym.doc:
        parts.append(f"— {sym.doc}")
    return ' '.join(parts)


def gather(repo_path: str, skip: set = None, source_budget: int = 8000) -> str:
    """Scan a codebase and produce structured output for feature synthesis."""
    cache = setup_engine()

    stats = cache.scan(repo_path, skip=skip)
    if stats['files'] == 0:
        return f"No parseable files found in {repo_path}"

    categories = classify_symbols(cache)
    key_files = identify_key_files(cache, source_budget)

    lines = []

    # ── Header
    root_name = Path(repo_path).name
    lines.append(f"# Structural Scan: {root_name}")
    lines.append(f"Files: {stats['files']} | Symbols: {stats['symbols']} | "
                 f"Languages: {', '.join(stats['languages'])}")
    lines.append("")

    # ── Directory structure
    lines.append("## Directory Structure")
    lines.append(cache.tree_overview())
    lines.append("")

    # ── Entry points
    if categories['entry_points']:
        lines.append("## Entry Points")
        for sym in categories['entry_points']:
            lines.append(format_symbol_brief(sym))
        lines.append("")

    # ── Public API (grouped by file)
    if categories['public_api']:
        lines.append("## Public API")
        by_file = {}
        for sym in categories['public_api']:
            by_file.setdefault(sym.file, []).append(sym)
        for filepath in sorted(by_file.keys()):
            lines.append(f"\n### {filepath}")
            for sym in by_file[filepath]:
                lines.append(format_symbol_brief(sym))
                for child in sym.children[:5]:  # cap method listings
                    lines.append(format_symbol_brief(child, indent=1))
                if len(sym.children) > 5:
                    lines.append(f"    ... +{len(sym.children) - 5} more methods")
        lines.append("")

    # ── Types
    if categories['types']:
        lines.append("## Types & Data Structures")
        for sym in categories['types']:
            lines.append(format_symbol_brief(sym))
            for child in sym.children[:5]:
                lines.append(format_symbol_brief(child, indent=1))
            if len(sym.children) > 5:
                lines.append(f"    ... +{len(sym.children) - 5} more")
        lines.append("")

    # ── Key file sources
    if key_files:
        lines.append("## Key Source Excerpts")
        lines.append(f"*{len(key_files)} files selected by structural importance*\n")
        for filepath in key_files:
            entry = cache.files.get(filepath)
            if not entry:
                continue
            source_text = entry.source.decode('utf-8', errors='replace')
            # For large files, show first ~150 lines
            source_lines = source_text.split('\n')
            if len(source_lines) > 150:
                excerpt = '\n'.join(source_lines[:150])
                lines.append(f"### {filepath} (first 150/{len(source_lines)} lines)")
            else:
                excerpt = source_text
                lines.append(f"### {filepath}")
            lines.append(f"```{entry.lang}")
            lines.append(excerpt)
            lines.append("```\n")

    # ── Import graph summary
    lines.append("## Import Graph (internal dependencies)")
    # Collect all module names that exist in the repo for internal detection
    repo_modules = set()
    for relpath in cache.files:
        # Convert file paths to potential module names
        stem = Path(relpath).stem
        if stem != '__init__':
            repo_modules.add(stem)
        parts = Path(relpath).parts
        for p in parts[:-1]:  # directory names
            repo_modules.add(p)

    for relpath, entry in sorted(cache.files.items()):
        if entry.lang == 'markdown':
            continue
        # Keep relative imports (start with .) and imports matching repo modules
        internal = [imp for imp in entry.imports
                    if imp.startswith('.') or
                    imp.split('.')[0] in repo_modules]
        if internal:
            lines.append(f"- {relpath} ← {', '.join(internal[:10])}")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Gather codebase structure for feature synthesis')
    parser.add_argument('repo', help='Path to codebase root')
    parser.add_argument('--skip', default='', help='Comma-separated dirs to skip')
    parser.add_argument('--source-budget', type=int, default=8000,
                        help='Approximate char budget for source excerpts (default: 8000)')
    args = parser.parse_args()

    skip = set(args.skip.split(',')) if args.skip else None
    print(gather(args.repo, skip=skip, source_budget=args.source_budget))


if __name__ == '__main__':
    main()
