#!/usr/bin/env python3
"""
check.py — Validate _FEATURES.md hierarchy against current codebase state.

Discovers all _FEATURES.md files (root + sub-files linked from parents),
parses symbol references, resolves them via tree-sitting, and reports:
  - Broken refs (symbol renamed, deleted, or moved)
  - Dead features (ALL key symbols gone)
  - Uncovered symbols (new public API not mentioned in any feature)
  - Orphan sub-files (_FEATURES.md files not linked from any parent)
  - Broken sub-file links (links to _FEATURES.md that don't exist)

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


def discover_features_files(root_path: Path, repo: Path) -> list:
    """Discover all _FEATURES.md files by following links from the root.

    Returns list of (path, linked_from) tuples.
    """
    # Start with the root
    discovered = [(root_path, None)]
    visited = {root_path.resolve()}

    # Sub-file link pattern: [text](path/to/_FEATURES.md) or (path/_FEATURES.md)
    link_pattern = re.compile(r'\]\(([^)]*_FEATURES\.md)\)')

    queue = [root_path]
    while queue:
        current = queue.pop(0)
        if not current.exists():
            continue

        text = current.read_text()
        parent_dir = current.parent

        for match in link_pattern.finditer(text):
            rel_link = match.group(1)
            linked_path = (parent_dir / rel_link).resolve()

            if linked_path not in visited:
                visited.add(linked_path)
                discovered.append((linked_path, str(current.relative_to(repo))))
                if linked_path.exists():
                    queue.append(linked_path)

    return discovered


def find_all_features_files(repo: Path) -> list:
    """Find ALL _FEATURES.md files in the repo, including unlinked ones."""
    return list(repo.rglob('_FEATURES.md'))


def parse_features_file(path: Path) -> dict:
    """Parse _FEATURES.md and extract structure.

    Returns:
        {
            'path': str,
            'features': [
                {
                    'name': str,
                    'line': int,
                    'refs': [{'file': str, 'symbol': str, 'line': int}, ...],
                },
                ...
            ],
            'all_refs': [{'file': str, 'symbol': str, 'feature': str, 'line': int, 'source_file': str}, ...],
            'sub_links': [{'target': str, 'line': int}, ...]
        }
    """
    text = path.read_text()
    lines = text.split('\n')

    ref_pattern = re.compile(r'`([^`]+?)#([^`]+?)`')
    link_pattern = re.compile(r'\]\(([^)]*_FEATURES\.md)\)')

    features = []
    all_refs = []
    sub_links = []
    current_feature = None

    for i, line in enumerate(lines, 1):
        # Feature headers are ## level
        if line.startswith('## ') and not line.startswith('### '):
            feature_name = line[3:].strip()
            if feature_name.lower() in ('feature inventory', 'status summary'):
                continue
            current_feature = {
                'name': feature_name,
                'line': i,
                'refs': [],
            }
            features.append(current_feature)

        # Extract symbol references
        for match in ref_pattern.finditer(line):
            filepath = match.group(1)
            symbol = match.group(2)
            ref = {
                'file': filepath,
                'symbol': symbol,
                'line': i,
                'feature': current_feature['name'] if current_feature else '(preamble)',
                'source_file': str(path),
            }
            if current_feature:
                current_feature['refs'].append(ref)
            all_refs.append(ref)

        # Extract sub-file links
        for match in link_pattern.finditer(line):
            sub_links.append({'target': match.group(1), 'line': i})

    return {
        'path': str(path),
        'features': features,
        'all_refs': all_refs,
        'sub_links': sub_links,
    }


def resolve_refs(cache, refs: list) -> tuple[list, list]:
    """Check each ref against the codebase.

    Returns (resolved, broken) where each is a list of ref dicts
    with an added 'match' key for resolved refs.
    """
    resolved = []
    broken = []

    for ref in refs:
        filepath = ref['file']
        symbol_parts = ref['symbol'].split('#')
        symbol_name = symbol_parts[-1]

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
            global_matches = cache.find_symbol(symbol_name, limit=3)
            if global_matches:
                ref['moved_to'] = global_matches[0].file
                ref['match'] = global_matches[0]
                found = True

        if found:
            resolved.append(ref)
        else:
            broken.append(ref)

    return resolved, broken


def find_uncovered(cache, all_refs: list, skip_patterns: set = None) -> list:
    """Find public symbols not referenced in any feature."""
    skip_patterns = skip_patterns or set()

    referenced = set()
    for ref in all_refs:
        parts = ref['symbol'].split('#')
        referenced.add(parts[-1])
        if len(parts) > 1:
            referenced.add(parts[0])

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
            for child in sym.children:
                if child.name.startswith('_'):
                    continue
                if child.name not in referenced:
                    if sym.name in referenced:
                        uncovered.append(child)

    return uncovered


def check(repo_path: str, features_path: str = None,
          skip: set = None, verbose: bool = False) -> dict:
    """Run all checks across the full _FEATURES.md hierarchy."""

    engine_path = _find_treesit_engine()
    if engine_path is None:
        print("ERROR: tree-sitting skill not found.", file=sys.stderr)
        sys.exit(1)
    sys.path.insert(0, str(engine_path))
    from engine import CodeCache

    repo = Path(repo_path).resolve()

    # Find root _FEATURES.md
    if features_path:
        root_fpath = Path(features_path)
    else:
        root_fpath = repo / '_FEATURES.md'
    if not root_fpath.exists():
        return {'error': f'_FEATURES.md not found at {root_fpath}'}

    # Discover linked hierarchy
    linked_files = discover_features_files(root_fpath, repo)

    # Find ALL _FEATURES.md files in repo (for orphan detection)
    all_files_on_disk = find_all_features_files(repo)
    linked_paths = {p.resolve() for p, _ in linked_files}

    # Parse all linked feature files
    all_features = []
    all_refs = []
    all_sub_links = []
    broken_sub_links = []
    file_count = 0

    for fpath, linked_from in linked_files:
        if not fpath.exists():
            broken_sub_links.append({
                'target': str(fpath.relative_to(repo)),
                'linked_from': linked_from or '(root)',
            })
            continue
        file_count += 1
        parsed = parse_features_file(fpath)
        all_features.extend(parsed['features'])
        all_refs.extend(parsed['all_refs'])

        # Check sub-links resolve
        for link in parsed['sub_links']:
            target = (fpath.parent / link['target']).resolve()
            if not target.exists():
                broken_sub_links.append({
                    'target': link['target'],
                    'linked_from': str(fpath.relative_to(repo)),
                    'line': link['line'],
                })

    # Detect orphan _FEATURES.md files
    orphans = [
        str(f.relative_to(repo))
        for f in all_files_on_disk
        if f.resolve() not in linked_paths
    ]

    # Scan codebase
    cache = CodeCache()
    cache.scan(str(repo), skip=skip)

    # Resolve refs
    resolved, broken = resolve_refs(cache, all_refs)

    # Find moved symbols
    moved = [r for r in resolved if 'moved_to' in r]

    # Find dead features
    dead_features = []
    for feat in all_features:
        if feat['refs'] and all(r in broken for r in feat['refs']):
            dead_features.append(feat)

    # Find uncovered symbols
    uncovered = find_uncovered(cache, all_refs)

    return {
        'features_files': file_count,
        'total_features': len(all_features),
        'total_refs': len(all_refs),
        'resolved': len(resolved),
        'broken': broken,
        'moved': moved,
        'dead_features': dead_features,
        'uncovered': uncovered,
        'orphan_files': orphans,
        'broken_sub_links': broken_sub_links,
        'clean': (len(broken) == 0 and len(broken_sub_links) == 0),
    }


def format_report(results: dict) -> str:
    """Format check results as readable report."""
    lines = []

    if 'error' in results:
        return f"ERROR: {results['error']}"

    lines.append(f"# _FEATURES.md Check")
    lines.append(f"Feature files: {results['features_files']} | "
                 f"Features: {results['total_features']} | "
                 f"Refs: {results['total_refs']} | "
                 f"Resolved: {results['resolved']} | "
                 f"Broken: {len(results['broken'])}")
    lines.append("")

    if results['clean'] and not results['moved'] and not results['orphan_files']:
        lines.append("✓ All symbol references resolve. No drift detected.")
    else:
        if results['broken']:
            lines.append(f"## Broken References ({len(results['broken'])})")
            for ref in results['broken']:
                source = ref.get('source_file', '')
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

        if results['broken_sub_links']:
            lines.append(f"## Broken Sub-File Links ({len(results['broken_sub_links'])})")
            for link in results['broken_sub_links']:
                from_str = link.get('linked_from', '?')
                lines.append(f"  ✗ `{link['target']}` linked from {from_str}")
            lines.append("")

    if results['orphan_files']:
        lines.append(f"## Orphan Feature Files ({len(results['orphan_files'])})")
        for orphan in results['orphan_files']:
            lines.append(f"  ? `{orphan}` — not linked from any parent _FEATURES.md")
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
                     "in any _FEATURES.md file.")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Check _FEATURES.md hierarchy against codebase')
    parser.add_argument('repo', help='Path to codebase root')
    parser.add_argument('--features', default=None, help='Path to root _FEATURES.md')
    parser.add_argument('--skip', default='', help='Comma-separated dirs to skip')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    skip = set(args.skip.split(',')) if args.skip else None
    results = check(args.repo, features_path=args.features, skip=skip, verbose=args.verbose)
    print(format_report(results))
    sys.exit(0 if results.get('clean', False) else 1)


if __name__ == '__main__':
    main()
