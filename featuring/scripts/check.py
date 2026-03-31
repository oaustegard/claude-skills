#!/usr/bin/env python3
"""
check.py — Validate _FEATURES.md against current codebase state.

Parses symbol references from _FEATURES.md, resolves them via tree-sitting,
and reports:
  - Broken refs (symbol renamed, deleted, or moved)
  - Dead features (ALL key symbols gone)
  - Uncovered symbols (new public API not mentioned in any feature)

Usage:
    python check.py /path/to/repo [--features _FEATURES.md] [--skip tests]

Exit codes: 0 = clean, 1 = drift detected
"""

import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict

# Reuse gather's engine discovery
from gather import _find_treesit_engine


def parse_features_file(path: Path) -> dict:
    """Parse _FEATURES.md and extract structure.

    Returns:
        {
            'features': [
                {
                    'name': str,
                    'line': int,
                    'refs': [{'file': str, 'symbol': str, 'line': int}, ...],
                },
                ...
            ],
            'all_refs': [{'file': str, 'symbol': str, 'feature': str, 'line': int}, ...]
        }
    """
    text = path.read_text()
    lines = text.split('\n')

    # Pattern: `file.py#symbol_name` or `file.py#Class#method`
    ref_pattern = re.compile(r'`([^`]+?)#([^`]+?)`')

    features = []
    all_refs = []
    current_feature = None

    for i, line in enumerate(lines, 1):
        # Feature headers are ## level
        if line.startswith('## ') and not line.startswith('### '):
            feature_name = line[3:].strip()
            # Skip non-feature headers like "Feature Inventory"
            if feature_name.lower() in ('feature inventory', 'status summary'):
                continue
            current_feature = {
                'name': feature_name,
                'line': i,
                'refs': [],
            }
            features.append(current_feature)

        # Extract symbol references from any line
        for match in ref_pattern.finditer(line):
            filepath = match.group(1)
            symbol = match.group(2)
            ref = {
                'file': filepath,
                'symbol': symbol,
                'line': i,
                'feature': current_feature['name'] if current_feature else '(preamble)',
            }
            if current_feature:
                current_feature['refs'].append(ref)
            all_refs.append(ref)

    return {'features': features, 'all_refs': all_refs}


def resolve_refs(cache, refs: list) -> tuple[list, list]:
    """Check each ref against the codebase.

    Returns (resolved, broken) where each is a list of ref dicts
    with an added 'match' key for resolved refs.
    """
    resolved = []
    broken = []

    for ref in refs:
        filepath = ref['file']
        symbol_parts = ref['symbol'].split('#')  # handles Class#method
        symbol_name = symbol_parts[-1]  # innermost name

        # Try exact file + symbol match
        file_syms = cache.file_symbols(filepath)
        found = False

        if file_syms:
            for sym in file_syms:
                if sym.name == symbol_name:
                    found = True
                    ref['match'] = sym
                    break
                for child in sym.children:
                    if child.name == symbol_name:
                        found = True
                        ref['match'] = child
                        break
                if found:
                    break

        if not found:
            # Fallback: search globally (symbol might have moved files)
            global_matches = cache.find_symbol(symbol_name, limit=3)
            if global_matches:
                ref['moved_to'] = global_matches[0].file
                ref['match'] = global_matches[0]
                found = True  # It exists, just moved

        if found:
            resolved.append(ref)
        else:
            broken.append(ref)

    return resolved, broken


def find_uncovered(cache, all_refs: list, skip_patterns: set = None) -> list:
    """Find public symbols not referenced in any feature.

    Returns list of Symbol objects that appear to be public API
    but aren't mentioned in _FEATURES.md.
    """
    skip_patterns = skip_patterns or set()

    # Build set of referenced symbol names
    referenced = set()
    for ref in all_refs:
        parts = ref['symbol'].split('#')
        referenced.add(parts[-1])
        if len(parts) > 1:
            referenced.add(parts[0])  # also mark the class as covered

    uncovered = []
    for relpath, entry in cache.files.items():
        if entry.lang == 'markdown':
            continue
        if any(p in relpath.lower() for p in ('test', 'spec', '__tests__', 'vendor')):
            continue
        if any(p in relpath for p in skip_patterns):
            continue

        for sym in entry.symbols:
            if sym.name.startswith('_'):
                continue
            if sym.name not in referenced:
                uncovered.append(sym)
            # Check children too (methods)
            for child in sym.children:
                if child.name.startswith('_'):
                    continue
                if child.name not in referenced:
                    # Only flag public methods of referenced classes
                    if sym.name in referenced:
                        uncovered.append(child)

    return uncovered


def check(repo_path: str, features_path: str = None,
          skip: set = None, verbose: bool = False) -> dict:
    """Run all checks. Returns results dict."""

    engine_path = _find_treesit_engine()
    if engine_path is None:
        print("ERROR: tree-sitting skill not found.", file=sys.stderr)
        sys.exit(1)
    sys.path.insert(0, str(engine_path))
    from engine import CodeCache

    repo = Path(repo_path).resolve()

    # Find _FEATURES.md
    if features_path:
        fpath = Path(features_path)
    else:
        fpath = repo / '_FEATURES.md'
    if not fpath.exists():
        return {'error': f'_FEATURES.md not found at {fpath}'}

    # Parse features
    parsed = parse_features_file(fpath)
    features = parsed['features']
    all_refs = parsed['all_refs']

    # Scan codebase
    cache = CodeCache()
    cache.scan(str(repo), skip=skip)

    # Resolve refs
    resolved, broken = resolve_refs(cache, all_refs)

    # Find moved symbols (broken ref but found elsewhere)
    moved = [r for r in resolved if 'moved_to' in r]

    # Find dead features (all refs broken)
    dead_features = []
    for feat in features:
        if feat['refs'] and all(r in broken for r in feat['refs']):
            dead_features.append(feat)

    # Find uncovered symbols
    uncovered = find_uncovered(cache, all_refs)

    return {
        'features_file': str(fpath),
        'total_features': len(features),
        'total_refs': len(all_refs),
        'resolved': len(resolved),
        'broken': broken,
        'moved': moved,
        'dead_features': dead_features,
        'uncovered': uncovered,
        'clean': len(broken) == 0,
    }


def format_report(results: dict) -> str:
    """Format check results as readable report."""
    lines = []

    if 'error' in results:
        return f"ERROR: {results['error']}"

    lines.append(f"# _FEATURES.md Check")
    lines.append(f"File: {results['features_file']}")
    lines.append(f"Features: {results['total_features']} | "
                 f"Refs: {results['total_refs']} | "
                 f"Resolved: {results['resolved']} | "
                 f"Broken: {len(results['broken'])}")
    lines.append("")

    if results['clean'] and not results['moved']:
        lines.append("✓ All symbol references resolve. No drift detected.")
    else:
        if results['broken']:
            lines.append(f"## Broken References ({len(results['broken'])})")
            for ref in results['broken']:
                lines.append(f"  ✗ `{ref['file']}#{ref['symbol']}` "
                             f"(line {ref['line']}, feature: {ref['feature']})")
            lines.append("")

        if results['moved']:
            lines.append(f"## Moved Symbols ({len(results['moved'])})")
            for ref in results['moved']:
                lines.append(f"  → `{ref['file']}#{ref['symbol']}` "
                             f"moved to `{ref['moved_to']}` "
                             f"(line {ref['line']}, feature: {ref['feature']})")
            lines.append("")

        if results['dead_features']:
            lines.append(f"## Dead Features ({len(results['dead_features'])})")
            for feat in results['dead_features']:
                lines.append(f"  ☠ **{feat['name']}** (line {feat['line']}) "
                             f"— all {len(feat['refs'])} refs broken")
            lines.append("")

    if results['uncovered']:
        lines.append(f"## Uncovered Public Symbols ({len(results['uncovered'])})")
        by_file = defaultdict(list)
        for sym in results['uncovered']:
            by_file[sym.file].append(sym)
        for filepath in sorted(by_file.keys()):
            syms = by_file[filepath]
            names = ', '.join(s.name for s in syms[:8])
            if len(syms) > 8:
                names += f', ... +{len(syms) - 8}'
            lines.append(f"  {filepath}: {names}")
        lines.append("")
        lines.append("These symbols appear in the public API but aren't referenced "
                     "in any _FEATURES.md section.")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Check _FEATURES.md against codebase')
    parser.add_argument('repo', help='Path to codebase root')
    parser.add_argument('--features', default=None, help='Path to _FEATURES.md (default: repo/_FEATURES.md)')
    parser.add_argument('--skip', default='', help='Comma-separated dirs to skip')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    skip = set(args.skip.split(',')) if args.skip else None
    results = check(args.repo, features_path=args.features, skip=skip, verbose=args.verbose)
    print(format_report(results))
    sys.exit(0 if results.get('clean', False) else 1)


if __name__ == '__main__':
    main()
