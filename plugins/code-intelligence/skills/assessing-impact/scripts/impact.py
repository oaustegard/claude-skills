#!/usr/bin/env python3
"""
impact.py — Pre-change blast-radius report for a symbol or file.

Given a target (symbol name or file path) in a local codebase, walks the
tree-sitting AST cache to find direct references, augments with a plain-text
scan of non-parsed file types (configs, plain docs), and clusters the
affected sites by feature (using `_FEATURES.md`) or by top-level directory.

Output: a structured markdown report intended as input to an LLM that will
synthesize the final risk summary. No opinionated risk score — the data is
presented; judgment is the LLM's job.

Usage:
    python impact.py /path/to/repo SYMBOL
    python impact.py /path/to/repo path/to/file.py
    python impact.py /path/to/repo SYMBOL --features _FEATURES.md
    python impact.py /path/to/repo SYMBOL --skip tests,vendor --json
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict


# Plain-text extensions that tree-sitting doesn't parse but may mention symbols.
NON_AST_EXTS = {
    '.txt', '.rst', '.cfg', '.ini', '.env', '.properties',
    '.dockerfile', '.makefile', '.mk', '.example', '.sample',
}
NON_AST_FILENAMES = {
    'Dockerfile', 'Makefile', 'Procfile', 'Caddyfile',
    '.env', '.gitignore', '.dockerignore',
}

# Files that document but rarely "use" a symbol — separate them in the report.
DOC_EXTS = {'.md', '.rst', '.txt', '.adoc'}

# Test path heuristics — these refs matter for "what tests exercise this?"
TEST_PATH_PATTERNS = re.compile(r'(^|/)(tests?|__tests__|spec|specs)(/|$)', re.IGNORECASE)
TEST_FILE_PATTERN = re.compile(r'(^|/)(test_|_test\.|\.test\.|\.spec\.)', re.IGNORECASE)


def _find_treesit_engine() -> Path | None:
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
    """Import tree-sitting engine. Exits on failure."""
    engine_path = _find_treesit_engine()
    if engine_path is None:
        print("ERROR: tree-sitting skill not found. Install it first.", file=sys.stderr)
        sys.exit(2)
    sys.path.insert(0, str(engine_path))
    try:
        from engine import CodeCache  # noqa: F401
        return CodeCache()
    except ImportError as e:
        print(f"ERROR: tree-sitting engine import failed: {e}", file=sys.stderr)
        sys.exit(2)


def is_test_path(relpath: str) -> bool:
    """Heuristic: does this path look like a test?"""
    return bool(TEST_PATH_PATTERNS.search(relpath) or TEST_FILE_PATTERN.search(relpath))


def is_doc_path(relpath: str) -> bool:
    return Path(relpath).suffix.lower() in DOC_EXTS


def resolve_target(cache, target: str) -> dict:
    """Resolve a target string to symbols and their definition sites.

    Returns:
        {
            'kind': 'symbol' | 'file',
            'name': str,
            'symbols': [Symbol, ...],   # for kind='symbol': matches; for 'file': all symbols in file
            'def_sites': [{'file', 'line_start', 'line_end', 'kind'}, ...]
        }
    """
    target_path = Path(target)
    is_file = (
        '/' in target
        or target_path.suffix
        or any(target == relpath or target == relpath.split('/')[-1]
               for relpath in cache.files)
    )

    if is_file:
        symbols = cache.file_symbols(target)
        if not symbols:
            return {'kind': 'file', 'name': target, 'symbols': [], 'def_sites': []}
        def_sites = [
            {'file': s.file, 'line_start': s.line,
             'line_end': s.end_line, 'kind': s.kind, 'name': s.name}
            for s in symbols
        ]
        return {'kind': 'file', 'name': target, 'symbols': symbols, 'def_sites': def_sites}

    matches = cache.find_symbol(target, limit=50)
    exact = [s for s in matches if s.name == target]
    syms = exact if exact else matches
    def_sites = [
        {'file': s.file, 'line_start': s.line,
         'line_end': s.end_line, 'kind': s.kind, 'name': s.name}
        for s in syms
    ]
    return {
        'kind': 'symbol',
        'name': target,
        'symbols': syms,
        'def_sites': def_sites,
        'exact_match': bool(exact),
    }


def find_ast_refs(cache, names: list[str], def_sites: list[dict],
                  limit_per_name: int = 500) -> list[dict]:
    """Use tree-sitting's text-scan refs over its parsed corpus.

    Excludes the definition lines themselves so refs are USES, not declarations.
    """
    def_set = {(d['file'], line)
               for d in def_sites
               for line in range(d['line_start'], d['line_end'] + 1)}

    refs = []
    seen = set()
    for name in names:
        for r in cache.references(name, limit=limit_per_name):
            key = (r['file'], r['line'])
            if key in def_set or key in seen:
                continue
            seen.add(key)
            refs.append({
                'file': r['file'],
                'line': r['line'],
                'text': r['text'],
                'symbol': name,
                'source': 'ast-cache',
            })
    return refs


def find_text_refs(repo: Path, names: list[str], skip: set[str],
                   already_scanned: set[str], limit: int = 500) -> list[dict]:
    """Plain-text scan of files NOT in the AST cache (configs, plain docs).

    Looks for whole-word occurrences of each name. Returns matches outside
    `already_scanned` (the set of cache-known relpaths).
    """
    if not names:
        return []
    pattern = re.compile(r'\b(' + '|'.join(re.escape(n) for n in names) + r')\b')
    refs = []

    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames
                       if d not in skip and not d.startswith('.')]
        for fn in filenames:
            fp = Path(dirpath) / fn
            try:
                relpath = str(fp.relative_to(repo))
            except ValueError:
                continue
            if relpath in already_scanned:
                continue
            ext = fp.suffix.lower()
            if not (ext in NON_AST_EXTS or ext in DOC_EXTS or fn in NON_AST_FILENAMES):
                continue
            try:
                text = fp.read_text(errors='replace')
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.split('\n'), 1):
                m = pattern.search(line)
                if m:
                    refs.append({
                        'file': relpath,
                        'line': i,
                        'text': line.strip()[:140],
                        'symbol': m.group(1),
                        'source': 'text-scan',
                    })
                    if len(refs) >= limit:
                        return refs
    return refs


def cluster_refs(refs: list[dict]) -> dict:
    """Group references into buckets: tests, docs, code-by-package."""
    buckets: dict = {
        'code': defaultdict(list),  # package/top-dir -> refs
        'tests': [],
        'docs': [],
    }
    for r in refs:
        relpath = r['file']
        if is_test_path(relpath):
            buckets['tests'].append(r)
        elif is_doc_path(relpath):
            buckets['docs'].append(r)
        else:
            parts = relpath.split('/')
            pkg = parts[0] if len(parts) > 1 else '(root)'
            buckets['code'][pkg].append(r)
    return buckets


def parse_features_file(path: Path) -> list[dict]:
    """Parse a _FEATURES.md and return [{'name', 'files': set[str]}, ...].

    Files are extracted from `file#symbol` refs in each feature section.
    """
    if not path.exists():
        return []
    text = path.read_text(errors='replace')
    ref_pattern = re.compile(r'`([^`]+?)#[^`]+?`')

    features = []
    current = None
    for line in text.split('\n'):
        if line.startswith('## ') and not line.startswith('### '):
            if current:
                features.append(current)
            current = {'name': line[3:].strip(), 'files': set()}
        elif current:
            for m in ref_pattern.finditer(line):
                current['files'].add(m.group(1))
    if current:
        features.append(current)
    return [f for f in features if f['files']]


def map_refs_to_features(refs: list[dict], features: list[dict]) -> dict:
    """Return {feature_name: [refs]}. Refs that match no feature are excluded."""
    out: dict = defaultdict(list)
    for r in refs:
        for f in features:
            if r['file'] in f['files']:
                out[f['name']].append(r)
    return dict(out)


def find_test_files_for_target(cache, target_name: str, def_files: set[str]) -> list[str]:
    """Find test files that reference the target — likely test surfaces."""
    test_files = set()
    for r in cache.references(target_name, limit=200):
        if is_test_path(r['file']):
            test_files.add(r['file'])
    # Also: tests living next to the def files
    for df in def_files:
        parent = str(Path(df).parent)
        for relpath in cache.files:
            if is_test_path(relpath) and relpath.startswith(parent):
                test_files.add(relpath)
    return sorted(test_files)


def render_report(target: dict, refs_by_source: dict, features_map: dict,
                  test_surfaces: list[str], stats: dict) -> str:
    """Render the markdown report."""
    lines = [f"# Impact Report: {target['name']}\n"]

    lines.append("## Target")
    lines.append(f"- Kind: `{target['kind']}`")
    if target['kind'] == 'symbol' and not target.get('exact_match', True):
        lines.append(f"- ⚠ No exact match for `{target['name']}` — falling back "
                     "to substring matches across multiple symbols. "
                     "Refs below are the union; expect noise. Re-run with a "
                     "more specific name to narrow.")
    if target['def_sites']:
        lines.append(f"- Definition sites ({len(target['def_sites'])}):")
        for d in target['def_sites'][:10]:
            lines.append(f"  - `{d['file']}:{d['line_start']}-{d['line_end']}` "
                         f"({d['kind']}: `{d['name']}`)")
        if len(target['def_sites']) > 10:
            lines.append(f"  - ... and {len(target['def_sites']) - 10} more")
    else:
        lines.append("- No definition found in scanned corpus.")
    lines.append("")

    ast_refs = refs_by_source.get('ast-cache', [])
    text_refs = refs_by_source.get('text-scan', [])
    all_refs = ast_refs + text_refs
    clustered = cluster_refs(all_refs)

    n_code = sum(len(v) for v in clustered['code'].values())
    lines.append(f"## Direct & Textual References ({len(all_refs)} total)")
    lines.append(f"- Code refs: **{n_code}** across **{len(clustered['code'])}** "
                 f"top-level package(s)")
    lines.append(f"- Test refs: **{len(clustered['tests'])}**")
    lines.append(f"- Doc refs:  **{len(clustered['docs'])}**")
    lines.append(f"- Of which from AST cache: {len(ast_refs)}; from plain-text scan: {len(text_refs)}")
    lines.append("")

    if clustered['code']:
        lines.append("### Code references by package")
        for pkg in sorted(clustered['code'].keys()):
            pkg_refs = clustered['code'][pkg]
            lines.append(f"\n**{pkg}/** — {len(pkg_refs)} refs in "
                         f"{len(set(r['file'] for r in pkg_refs))} files")
            for r in pkg_refs[:15]:
                lines.append(f"- `{r['file']}:{r['line']}` — {r['text']}")
            if len(pkg_refs) > 15:
                lines.append(f"- ... and {len(pkg_refs) - 15} more")
        lines.append("")

    if clustered['tests']:
        lines.append("### Test references")
        for r in clustered['tests'][:20]:
            lines.append(f"- `{r['file']}:{r['line']}` — {r['text']}")
        if len(clustered['tests']) > 20:
            lines.append(f"- ... and {len(clustered['tests']) - 20} more")
        lines.append("")

    if clustered['docs']:
        lines.append("### Documentation mentions")
        for r in clustered['docs'][:15]:
            lines.append(f"- `{r['file']}:{r['line']}` — {r['text']}")
        if len(clustered['docs']) > 15:
            lines.append(f"- ... and {len(clustered['docs']) - 15} more")
        lines.append("")

    if features_map:
        lines.append("## Affected Features (from `_FEATURES.md`)")
        for name, frefs in sorted(features_map.items(),
                                  key=lambda kv: -len(kv[1])):
            files = sorted(set(r['file'] for r in frefs))
            lines.append(f"- **{name}** — {len(frefs)} refs across {len(files)} file(s)")
        lines.append("")

    if test_surfaces:
        lines.append("## Suggested Test Surfaces")
        for tf in test_surfaces[:20]:
            lines.append(f"- `{tf}`")
        if len(test_surfaces) > 20:
            lines.append(f"- ... and {len(test_surfaces) - 20} more")
        lines.append("")

    lines.append("## Caveats")
    lines.append("- **Text-based ref discovery.** Matches are by symbol name. "
                 "Common names (e.g. `run`, `init`) will produce noisy matches "
                 "from unrelated symbols with the same identifier.")
    lines.append("- **No type/MRO resolution.** Method calls dispatched on a "
                 "dynamic type (e.g. `obj.foo()` where `obj`'s class isn't "
                 "knowable statically) may be missed or over-matched.")
    lines.append("- **No cross-language tracing.** A TS frontend calling a "
                 "Python backend handler over HTTP won't be linked.")
    lines.append("- **Single-repo only.** Anything in a separate repo "
                 "(consumer, vendored package) is invisible.")
    lines.append("- **Corpus**: " + (", ".join(stats.get('languages', [])) or "(none)") +
                 f" — {stats.get('files', 0)} parsed files, "
                 f"{stats.get('symbols', 0)} symbols.")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Pre-change blast-radius report for a symbol or file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('repo', help="Path to the repository root.")
    parser.add_argument('target', help="Symbol name or file path.")
    parser.add_argument('--features', default='_FEATURES.md',
                        help="Path to root _FEATURES.md (default: _FEATURES.md).")
    parser.add_argument('--skip', default='',
                        help="Comma-separated extra dirs to skip during scan.")
    parser.add_argument('--limit-per-name', type=int, default=500,
                        help="Max refs per symbol name (default: 500).")
    parser.add_argument('--json', action='store_true',
                        help="Emit a JSON document instead of markdown.")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"ERROR: not a directory: {repo}", file=sys.stderr)
        sys.exit(2)

    cache = setup_engine()
    from engine import DEFAULT_SKIP  # noqa: E402
    skip_set = set(DEFAULT_SKIP)
    if args.skip:
        skip_set.update(s.strip() for s in args.skip.split(',') if s.strip())
    stats = cache.scan(str(repo), skip=skip_set)

    target = resolve_target(cache, args.target)
    if not target['symbols']:
        print(f"ERROR: target '{args.target}' not found as symbol or file in "
              f"{stats.get('files', 0)} parsed files.", file=sys.stderr)
        sys.exit(1)

    names = sorted({s.name for s in target['symbols']})
    ast_refs = find_ast_refs(cache, names, target['def_sites'],
                             limit_per_name=args.limit_per_name)
    text_refs = find_text_refs(repo, names, skip_set,
                               already_scanned=set(cache.files.keys()),
                               limit=args.limit_per_name * len(names))

    features_path = repo / args.features
    features = parse_features_file(features_path)
    features_map = map_refs_to_features(ast_refs + text_refs, features) if features else {}

    primary_name = target['name'] if target['kind'] == 'symbol' else names[0]
    def_files = {d['file'] for d in target['def_sites']}
    test_surfaces = find_test_files_for_target(cache, primary_name, def_files)

    refs_by_source = {'ast-cache': ast_refs, 'text-scan': text_refs}

    if args.json:
        out = {
            'target': {
                'kind': target['kind'],
                'name': target['name'],
                'def_sites': target['def_sites'],
            },
            'refs': {
                'ast_cache': ast_refs,
                'text_scan': text_refs,
            },
            'clusters': {
                pkg: refs for pkg, refs in cluster_refs(ast_refs + text_refs)['code'].items()
            },
            'features': {name: refs for name, refs in features_map.items()},
            'test_surfaces': test_surfaces,
            'stats': stats,
        }
        print(json.dumps(out, indent=2, default=str))
    else:
        print(render_report(target, refs_by_source, features_map,
                            test_surfaces, stats))


if __name__ == '__main__':
    main()
