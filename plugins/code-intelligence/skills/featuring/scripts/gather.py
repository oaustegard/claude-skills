#!/usr/bin/env python3
"""
gather.py — Collect structural data from a codebase via tree-sitting for feature synthesis.

Scans a codebase with tree-sitting's engine, then outputs a structured summary
optimized for LLM consumption: entry points, public APIs, symbol clusters by
directory, and selective source excerpts for key files.

Supports two modes:
  - Full scan: entire codebase → root _FEATURES.md synthesis
  - Area scan: specific subdirectory or file set → sub-feature file synthesis

Usage:
    # Full repo scan
    python gather.py /path/to/repo [--skip tests,.github] [--source-budget 8000]

    # Area scan (specific capability area)
    python gather.py /path/to/repo --area src/memory --source-budget 4000

Output: structured markdown to stdout, suitable as LLM prompt input.
"""

import sys
import os
import argparse
from pathlib import Path


def _find_treesit_engine():
    """Locate tree-sitting engine across known skill directories."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / 'tree-sitting' / 'scripts',
        Path('/mnt/skills/user/tree-sitting/scripts'),
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


def classify_symbols(cache, area_prefix=None) -> dict:
    """Classify symbols into feature-relevant categories.

    If area_prefix is set, only include symbols from files under that path.
    """
    categories = {
        'entry_points': [],
        'public_api': [],
        'types': [],
        'constants': [],
        'tests': [],
        'internal': [],
    }

    entry_patterns = {'main', 'cli', 'run', 'serve', 'start', 'app', 'init', 'setup', 'boot'}
    test_patterns = {'test_', 'test', 'spec_', 'it_'}

    for relpath, entry in cache.files.items():
        # Area filter
        if area_prefix and not relpath.startswith(area_prefix):
            continue
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


def identify_key_files(cache, source_budget: int, area_prefix=None) -> list:
    """Pick files worth reading source from, within a token budget."""
    file_scores = []
    for relpath, entry in cache.files.items():
        if area_prefix and not relpath.startswith(area_prefix):
            continue
        if any(p in relpath.lower() for p in ('test', 'spec', '__tests__', 'vendor', 'node_modules')):
            continue
        if entry.lang in ('json', 'yaml', 'toml', 'css', 'html', 'markdown'):
            continue

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

    file_scores.sort(key=lambda x: x[1], reverse=True)
    selected = []
    remaining = source_budget
    for relpath, score, size in file_scores:
        char_estimate = size
        if char_estimate <= remaining:
            selected.append(relpath)
            remaining -= char_estimate
        elif remaining > 2000:
            selected.append(relpath)
            break
    return selected


def compute_complexity(cache, area_prefix=None) -> dict:
    """Compute complexity metrics to help decide hierarchy.

    Returns dict with counts and a suggested decomposition.
    """
    public_count = 0
    file_count = 0
    type_count = 0
    dir_symbols = {}  # dir → count of public symbols

    for relpath, entry in cache.files.items():
        if area_prefix and not relpath.startswith(area_prefix):
            continue
        if entry.lang in ('json', 'yaml', 'toml', 'css', 'html', 'markdown'):
            continue
        if any(p in relpath.lower() for p in ('test', 'spec', '__tests__', 'vendor')):
            continue

        file_count += 1
        parent = str(Path(relpath).parent) if '/' in relpath else '.'

        for sym in entry.symbols:
            if sym.name.startswith('_'):
                continue
            public_count += 1
            dir_symbols[parent] = dir_symbols.get(parent, 0) + 1
            if sym.kind in ('class', 'struct', 'enum', 'interface', 'trait', 'type'):
                type_count += 1

    # Suggest decomposition if complex enough
    suggestions = []
    if public_count > 30:
        # Find directory clusters with significant symbol counts
        for d, count in sorted(dir_symbols.items(), key=lambda x: -x[1]):
            if count >= 6:
                suggestions.append((d, count))

    return {
        'public_symbols': public_count,
        'files': file_count,
        'types': type_count,
        'dir_clusters': dir_symbols,
        'decomposition_candidates': suggestions,
        'needs_hierarchy': public_count > 20 or len(suggestions) > 2,
    }


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


def gather(repo_path: str, skip: set = None, source_budget: int = 8000,
           area: str = None) -> str:
    """Scan a codebase and produce structured output for feature synthesis.

    Args:
        repo_path: Root of the codebase to scan
        skip: Directory names to skip
        source_budget: Approximate char budget for source excerpts
        area: Optional subdirectory to focus on (for sub-feature generation)
    """
    cache = setup_engine()

    stats = cache.scan(repo_path, skip=skip)
    if stats['files'] == 0:
        return f"No parseable files found in {repo_path}"

    # Normalize area prefix
    area_prefix = area.rstrip('/') + '/' if area else None
    if area_prefix == './':
        area_prefix = None

    categories = classify_symbols(cache, area_prefix)
    key_files = identify_key_files(cache, source_budget, area_prefix)
    complexity = compute_complexity(cache, area_prefix)

    lines = []

    # ── Header
    root_name = Path(repo_path).name
    if area:
        lines.append(f"# Structural Scan: {root_name}/{area}")
    else:
        lines.append(f"# Structural Scan: {root_name}")
    lines.append(f"Files: {stats['files']} | Symbols: {stats['symbols']} | "
                 f"Languages: {', '.join(stats['languages'])}")
    lines.append("")

    # ── Complexity assessment (helps LLM decide hierarchy)
    lines.append("## Complexity Assessment")
    lines.append(f"Public symbols: {complexity['public_symbols']} | "
                 f"Source files: {complexity['files']} | "
                 f"Types: {complexity['types']}")
    if complexity['needs_hierarchy']:
        lines.append(f"**Hierarchy recommended.** This codebase has enough complexity "
                     f"for sub-feature files.")
        if complexity['decomposition_candidates']:
            lines.append("\nCandidate areas for sub-files (by symbol density):")
            for d, count in complexity['decomposition_candidates']:
                lines.append(f"  - `{d}/` — {count} public symbols")
    else:
        lines.append("**Flat structure sufficient.** A single _FEATURES.md should work.")
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
                for child in sym.children[:5]:
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
    repo_modules = set()
    for relpath in cache.files:
        stem = Path(relpath).stem
        if stem != '__init__':
            repo_modules.add(stem)
        parts = Path(relpath).parts
        for p in parts[:-1]:
            repo_modules.add(p)

    for relpath, entry in sorted(cache.files.items()):
        if area_prefix and not relpath.startswith(area_prefix):
            continue
        if entry.lang == 'markdown':
            continue
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
    parser.add_argument('--area', default=None,
                        help='Focus on a specific subdirectory (for sub-feature generation)')
    parser.add_argument('--source-budget', type=int, default=8000,
                        help='Approximate char budget for source excerpts (default: 8000)')
    args = parser.parse_args()

    skip = set(args.skip.split(',')) if args.skip else None
    print(gather(args.repo, skip=skip, source_budget=args.source_budget, area=args.area))


if __name__ == '__main__':
    main()
