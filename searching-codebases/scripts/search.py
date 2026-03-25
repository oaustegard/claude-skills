#!/usr/bin/env python3
"""
Unified code search: regex (n-gram indexed) and semantic (TF-IDF).

Usage:
    # Auto-detect query type
    python search.py /path/to/repo "def handle_error"
    python search.py /path/to/repo "retry logic with backoff"

    # Explicit mode
    python search.py /path/to/repo "class.*Error" --regex
    python search.py /path/to/repo "error handling" --semantic

    # Multiple queries
    python search.py /path/to/repo "def test_" "import os" "TODO|FIXME"

    # GitHub repo
    python search.py https://github.com/org/repo "authentication flow"

    # Structure overview only (delegates to mapping-codebases)
    python search.py /path/to/repo --map-only

    # Expand to full function bodies (default: signatures only)
    python search.py /path/to/repo "query" --expand

    # Benchmark regex search: indexed vs brute-force
    python search.py /path/to/repo "pattern" --benchmark

    # JSON output
    python search.py /path/to/repo "query" --json
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

# Add script directory to path
sys.path.insert(0, os.path.dirname(__file__))

from resolve import resolve, count_files


# Regex metacharacters that signal "this is a regex, not natural language"
_REGEX_META = {'*', '+', '?', '[', ']', '(', ')', '{', '}', '|', '^', '$', '\\', '.'}
# Only flag as regex if the "exotic" ones appear (not just . or parens)
_STRONG_REGEX_META = {'*', '+', '?', '[', ']', '{', '}', '^', '$', '\\', '|'}


def detect_mode(query: str) -> str:
    """
    Heuristic: is this query a regex/literal or a conceptual search?

    Returns "regex" or "semantic".
    """
    # Explicit regex markers
    if any(c in query for c in _STRONG_REGEX_META):
        return "regex"

    # Short queries with code-like tokens → regex (literal search)
    words = query.split()
    if len(words) <= 3:
        # Looks like code: contains underscores, dots, camelCase, parens
        if any(c in query for c in "_.()"):
            return "regex"
        # Single identifier
        if len(words) == 1:
            return "regex"

    # Multi-word queries without code markers → semantic
    if len(words) >= 3:
        return "semantic"

    return "regex"


def run_map(root: str, skip: str = None):
    """Generate structural maps by delegating to mapping-codebases."""
    codemap = None
    for candidate in [
        "/mnt/skills/user/mapping-codebases/scripts/codemap.py",
        os.path.join(os.path.dirname(__file__), "..", "..", "mapping-codebases", "scripts", "codemap.py"),
    ]:
        if os.path.isfile(candidate):
            codemap = candidate
            break

    if not codemap:
        print("Warning: mapping-codebases not found, skipping structural maps", file=sys.stderr)
        return

    # Ensure tree-sitter is available
    venv_python = "/home/claude/.venv/bin/python"
    if not os.path.isfile(venv_python):
        subprocess.run(["uv", "venv", "/home/claude/.venv"], capture_output=True)
        subprocess.run(
            ["uv", "pip", "install", "tree-sitter-language-pack",
             "--python", venv_python],
            capture_output=True,
        )

    cmd = [venv_python, codemap, root]
    if skip:
        cmd.extend(["--skip", skip])
    subprocess.run(cmd, capture_output=True)


def search_regex(root: str, queries: list, expand: bool = False,
                 benchmark: bool = False, verbose: bool = False,
                 skip_dirs: set = None) -> dict:
    """
    Regex/literal search using sparse n-gram index.

    Returns {query: [matches]} where each match has file, line, text,
    and optionally context (expanded function).
    """
    from ngram_index import NgramIndex, _brute_force_search

    # Build index
    index = NgramIndex()
    file_count = count_files(root, skip_dirs)

    # Skip indexing for tiny codebases — just use ripgrep directly
    if file_count < 20 and not benchmark:
        if verbose:
            print(f"Small codebase ({file_count} files), using direct search", file=sys.stderr)
        results = {}
        for q in queries:
            from ngram_index import _brute_force_search, DEFAULT_SKIP_DIRS
            matches = _brute_force_search(q, root, skip_dirs or DEFAULT_SKIP_DIRS)
            results[q] = _maybe_expand(matches, root, expand)
        return results

    index.build(root, skip_dirs=skip_dirs,
                use_frequency_weights=True, verbose=verbose)

    if verbose:
        s = index.stats
        print(f"Index: {s['files_indexed']} files, {s['unique_ngrams']:,} n-grams, "
              f"{s['index_time_ms']:.0f}ms", file=sys.stderr)

    results = {}
    for q in queries:
        if benchmark:
            _run_benchmark(index, q, root, skip_dirs or set())
        else:
            matches = index.search(q, root, max_results=500, verbose=verbose)
            results[q] = _maybe_expand(matches, root, expand)

    return results


def search_semantic(root: str, queries: list, expand: bool = False,
                    verbose: bool = False, skip_dirs: set = None) -> dict:
    """
    Semantic search using TF-IDF over code chunks.

    Returns {query: [matches]} with file, line, text, score.
    """
    # Ensure sklearn is available
    try:
        from code_rag import Index
    except ImportError:
        subprocess.run(
            ["uv", "pip", "install", "scikit-learn", "--system"],
            capture_output=True,
        )
        from code_rag import Index

    index = Index()
    index.build(root, skip_dirs=skip_dirs)

    if verbose:
        s = index.stats()
        print(f"TF-IDF index: {s.get('chunks', 0)} chunks, {s.get('vocabulary', 0)} terms, "
              f"{s.get('build_ms', 0)}ms", file=sys.stderr)

    results = {}
    for q in queries:
        hits = index.search(q, top_k=20)
        matches = []
        for chunk, score in hits:
            matches.append({
                "file": os.path.join(root, chunk.file) if not os.path.isabs(chunk.file) else chunk.file,
                "line": chunk.line,
                "text": chunk.text[:200],
                "score": round(score, 4),
                "kind": chunk.kind,
                "name": chunk.name,
            })
        results[q] = matches

    return results


def _maybe_expand(matches: list, root: str, expand: bool) -> list:
    """Optionally expand matches to full function context."""
    if not expand:
        return matches

    from context import expand_match, deduplicate_contexts

    contexts = []
    for m in matches:
        ctx = expand_match(m["file"], m["line"], root, signatures_only=False)
        if ctx:
            m["context"] = {
                "name": ctx.name,
                "type": ctx.node_type,
                "start_line": ctx.start_line,
                "end_line": ctx.end_line,
                "source": ctx.source,
            }
    return matches


def _run_benchmark(index, pattern, root, skip_dirs):
    """Compare indexed search vs brute-force ripgrep."""
    from ngram_index import _brute_force_search

    t0 = time.monotonic()
    indexed = index.search(pattern, root, max_results=5000, verbose=False)
    t_idx = (time.monotonic() - t0) * 1000

    t0 = time.monotonic()
    brute = _brute_force_search(pattern, root, skip_dirs, max_results=5000)
    t_brute = (time.monotonic() - t0) * 1000

    idx_files = {m["file"] for m in indexed}
    brute_files = {m["file"] for m in brute}
    missed = brute_files - idx_files

    print(f"\n{'='*60}")
    print(f"BENCHMARK: '{pattern}'")
    print(f"{'='*60}")
    print(f"  Indexed:  {t_idx:8.1f}ms  ({len(indexed)} matches, {len(idx_files)} files)")
    print(f"  Brute rg: {t_brute:8.1f}ms  ({len(brute)} matches, {len(brute_files)} files)")
    if t_brute > 0:
        print(f"  Speedup:  {t_brute / max(t_idx, 0.1):.1f}x")
    if missed:
        print(f"  ⚠ Missed: {len(missed)} files")
    elif not (idx_files - brute_files):
        print(f"  ✓ Results match")


def format_results(results: dict, root: str, output_json: bool = False) -> str:
    """Format search results for display."""
    if output_json:
        # Make paths relative
        for q, matches in results.items():
            for m in matches:
                try:
                    m["file"] = os.path.relpath(m["file"], root)
                except ValueError:
                    pass
        return json.dumps(results, indent=2)

    lines = []
    for query, matches in results.items():
        if len(results) > 1:
            lines.append(f"\n--- {query} ---")

        if not matches:
            lines.append("No matches found.")
            continue

        lines.append(f"{len(matches)} match{'es' if len(matches) != 1 else ''}")

        for m in matches[:30]:
            try:
                rel = os.path.relpath(m["file"], root)
            except ValueError:
                rel = m["file"]

            if "score" in m:
                lines.append(f"  {rel}:{m['line']}  [{m['score']:.3f}]  {m.get('name', '')}")
            else:
                text = m["text"][:150].rstrip()
                lines.append(f"  {rel}:{m['line']}: {text}")

            if "context" in m:
                ctx = m["context"]
                lines.append(f"    → {ctx['type']} {ctx['name']} "
                             f"(lines {ctx['start_line']}-{ctx['end_line']})")

        if len(matches) > 30:
            lines.append(f"  ... and {len(matches) - 30} more")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Unified code search")
    parser.add_argument("source", help="Path, GitHub URL, 'uploads', or 'project'")
    parser.add_argument("queries", nargs="*", help="Search queries")
    parser.add_argument("--regex", action="store_true", help="Force regex mode")
    parser.add_argument("--semantic", action="store_true", help="Force semantic mode")
    parser.add_argument("--map-only", action="store_true", help="Generate structural maps only")
    parser.add_argument("--expand", action="store_true", help="Expand to full function bodies")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark indexed vs brute-force")
    parser.add_argument("--branch", default="main", help="Git branch for GitHub URLs")
    parser.add_argument("--skip", default=None, help="Comma-separated directories to skip")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    # Resolve source
    root = resolve(args.source, args.branch)
    if args.verbose:
        print(f"Resolved: {root} ({count_files(root)} files)", file=sys.stderr)

    skip_dirs = None
    if args.skip:
        skip_dirs = set(args.skip.split(","))

    # Map-only mode
    if args.map_only:
        run_map(root, args.skip)
        print(f"Maps generated in {root}")
        return

    if not args.queries:
        parser.error("Provide at least one query, or use --map-only")

    # Route queries
    all_results = {}
    for query in args.queries:
        if args.regex:
            mode = "regex"
        elif args.semantic:
            mode = "semantic"
        else:
            mode = detect_mode(query)

        if args.verbose:
            print(f"Query: '{query}' → {mode} mode", file=sys.stderr)

    # Batch by mode for efficiency (one index build per mode)
    regex_queries = []
    semantic_queries = []
    for query in args.queries:
        if args.regex:
            regex_queries.append(query)
        elif args.semantic:
            semantic_queries.append(query)
        else:
            mode = detect_mode(query)
            if mode == "regex":
                regex_queries.append(query)
            else:
                semantic_queries.append(query)

    if regex_queries:
        results = search_regex(root, regex_queries, expand=args.expand,
                               benchmark=args.benchmark, verbose=args.verbose,
                               skip_dirs=skip_dirs)
        all_results.update(results)

    if semantic_queries:
        # Generate maps first for enriched TF-IDF
        run_map(root, args.skip)
        results = search_semantic(root, semantic_queries, expand=args.expand,
                                  verbose=args.verbose, skip_dirs=skip_dirs)
        all_results.update(results)

    if not args.benchmark:
        print(format_results(all_results, root, args.json))


if __name__ == "__main__":
    main()
