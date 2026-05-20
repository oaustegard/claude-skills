#!/usr/bin/env python3
"""
bm25.py — ranked content search over any corpus, powered by bm25s.

Stateless: each invocation walks the corpus, builds an index in memory,
runs the queries, prints results, exits. No persistence, no cache.

CORPUS is one of:
  - a local directory path
  - "uploads" → /mnt/user-data/uploads
  - "project" → /mnt/project
  - "github.com/owner/repo[@ref]" → fetches tarball, indexes contents

Queries are positional. Each runs against the same in-memory index.

Examples:
  bm25.py ./repo 'csrf middleware'
  bm25.py ./repo 'auth flow' 'session backend' --top-k 5
  bm25.py github.com/django/django 'queryset filter' --exclude 'tests/*'
  bm25.py /mnt/project 'rag scaling laws' --include '*.md'
  bm25.py ./repo --interactive
"""
import argparse
import fnmatch
import json
import os
import re
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

try:
    import bm25s
except ImportError:
    sys.stderr.write("bm25s not installed. Run: uv pip install --system --break-system-packages bm25s\n")
    sys.exit(2)


# ---------- corpus walking ----------

DEFAULT_TEXT_EXTS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.rb', '.java', '.c',
    '.cpp', '.h', '.hpp', '.cs', '.kt', '.swift', '.scala', '.php', '.lua',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd', '.sql',
    '.md', '.markdown', '.rst', '.txt', '.org', '.adoc',
    '.html', '.htm', '.xml', '.svg', '.css', '.scss', '.less',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.env',
    '.r', '.R', '.jl', '.dart', '.ex', '.exs', '.erl', '.hs', '.ml', '.mli',
    '.proto', '.tf', '.tfvars', '.dockerfile', '.makefile', '.cmake',
    '.csv', '.tsv', '.jsonl', '.ndjson',
}

DEFAULT_SKIP_DIRS = {
    '.git', '.hg', '.svn', '__pycache__', 'node_modules', '.venv', 'venv',
    '.tox', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'dist', 'build',
    '.next', '.nuxt', '.cache', 'target', '.idea', '.vscode',
}


def discover_files(root: Path, include_globs, exclude_globs, max_bytes: int):
    """Walk root, yield (relative_path, text) pairs. UTF-8 with replacement."""
    for dirpath, dirnames, filenames in os.walk(root):
        # prune
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_SKIP_DIRS]
        for fname in filenames:
            fp = Path(dirpath) / fname
            rel = fp.relative_to(root).as_posix()
            # include/exclude filters
            if include_globs and not any(fnmatch.fnmatch(rel, g) for g in include_globs):
                # also accept matches on basename
                if not any(fnmatch.fnmatch(fname, g) for g in include_globs):
                    continue
            if exclude_globs and any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(fname, g) for g in exclude_globs):
                continue
            # if no include filter and no recognized ext, skip
            if not include_globs and fp.suffix.lower() not in DEFAULT_TEXT_EXTS and fname.lower() not in ('makefile', 'dockerfile', 'readme'):
                continue
            try:
                if fp.stat().st_size > max_bytes:
                    continue
                text = fp.read_text(encoding='utf-8', errors='replace')
            except (OSError, PermissionError):
                continue
            yield rel, text


# ---------- corpus resolution ----------

GH_URL_RE = re.compile(r'^(?:https?://)?github\.com/([^/]+)/([^/@]+?)(?:@(\S+))?$')


def resolve_corpus(spec: str) -> Path:
    """Resolve a CORPUS spec to a local directory. Downloads tarballs for github.com/... specs."""
    if spec == 'uploads':
        return Path('/mnt/user-data/uploads')
    if spec == 'project':
        return Path('/mnt/project')
    m = GH_URL_RE.match(spec)
    if m:
        owner, repo, ref = m.group(1), m.group(2), m.group(3) or 'main'
        tmpdir = Path(tempfile.mkdtemp(prefix=f'bm25-{repo}-'))
        tar_path = tmpdir / f'{repo}.tar.gz'
        url = f'https://api.github.com/repos/{owner}/{repo}/tarball/{ref}'
        sys.stderr.write(f"[bm25] fetching {url} ...\n")
        req = urllib.request.Request(url)
        token = os.environ.get('GH_TOKEN')
        if token:
            req.add_header('Authorization', f'token {token}')
            req.add_header('User-Agent', 'muninn-raven')
        with urllib.request.urlopen(req) as r, open(tar_path, 'wb') as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        extract_dir = tmpdir / 'extract'
        extract_dir.mkdir()
        with tarfile.open(tar_path) as tar:
            tar.extractall(extract_dir)
        # tarball top-level is owner-repo-sha; descend into it
        subs = list(extract_dir.iterdir())
        if len(subs) == 1 and subs[0].is_dir():
            return subs[0]
        return extract_dir
    p = Path(spec).expanduser().resolve()
    if not p.is_dir():
        sys.stderr.write(f"[bm25] corpus not found or not a directory: {spec}\n")
        sys.exit(2)
    return p


# ---------- index ----------

class CorpusIndex:
    """In-memory BM25 index over a corpus. Stateless across invocations."""

    def __init__(self, corpus_root: Path, include, exclude, max_bytes=2_000_000):
        self.root = corpus_root
        self.paths = []      # parallel to docs
        self.docs = []
        t0 = time.time()
        for rel, text in discover_files(corpus_root, include, exclude, max_bytes):
            self.paths.append(rel)
            self.docs.append(text)
        self.discover_s = time.time() - t0
        t0 = time.time()
        tokens = bm25s.tokenize(self.docs, stopwords=None, show_progress=False)
        self.retriever = bm25s.BM25()
        self.retriever.index(tokens, show_progress=False)
        self.index_s = time.time() - t0

    def query(self, q: str, k: int = 10):
        tokens = bm25s.tokenize([q], stopwords=None, show_progress=False)
        idxs, scores = self.retriever.retrieve(tokens, k=min(k, len(self.docs)), show_progress=False)
        return [(int(i), float(s)) for i, s in zip(idxs[0], scores[0])]


# ---------- snippet extraction ----------

def best_snippet(doc: str, q: str, lines: int = 3) -> str:
    """Pick the best matching span — line containing the most query tokens, with context."""
    if lines <= 0:
        return ''
    q_terms = {t.lower() for t in re.findall(r'\w+', q) if len(t) > 1}
    if not q_terms:
        return doc[:200] + ('...' if len(doc) > 200 else '')
    doc_lines = doc.splitlines()
    best_i, best_score = 0, -1
    for i, line in enumerate(doc_lines):
        line_terms = {t.lower() for t in re.findall(r'\w+', line)}
        hits = len(line_terms & q_terms)
        if hits > best_score:
            best_score = hits
            best_i = i
    half = max(0, lines // 2)
    lo = max(0, best_i - half)
    hi = min(len(doc_lines), best_i + half + 1)
    return '\n'.join(doc_lines[lo:hi])


# ---------- output ----------

def print_results(idx: CorpusIndex, q: str, hits, snippet_lines: int, as_json: bool):
    if as_json:
        out = {'query': q, 'results': [
            {'path': idx.paths[i], 'score': s, 'snippet': best_snippet(idx.docs[i], q, snippet_lines)}
            for i, s in hits
        ]}
        print(json.dumps(out, indent=2))
        return
    print(f"\nQUERY: {q}")
    print("-" * 70)
    for rank, (i, s) in enumerate(hits, 1):
        path = idx.paths[i]
        snip = best_snippet(idx.docs[i], q, snippet_lines)
        snip_disp = ''
        if snip:
            snip_disp = '\n    ' + snip.replace('\n', '\n    ')
        print(f"  {rank}. {s:6.2f}  {path}{snip_disp}")


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(prog='bm25', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('corpus', help='directory, "uploads", "project", or github.com/owner/repo[@ref]')
    ap.add_argument('queries', nargs='*', help='one or more queries to run')
    ap.add_argument('--top-k', type=int, default=10, help='results per query (default 10)')
    ap.add_argument('--include', action='append', default=[], help='glob to include (repeat for multiple)')
    ap.add_argument('--exclude', action='append', default=[], help='glob to exclude (repeat for multiple)')
    ap.add_argument('--snippet-lines', type=int, default=3, help='lines of snippet context (0 = none)')
    ap.add_argument('--max-file-bytes', type=int, default=2_000_000, help='skip files larger than this')
    ap.add_argument('--json', action='store_true', help='machine-readable output')
    ap.add_argument('--interactive', '-i', action='store_true', help='REPL: query, q, query, q, ... (one corpus, many queries)')
    ap.add_argument('--stats', action='store_true', help='print discover/index timings')
    args = ap.parse_args()

    if not args.queries and not args.interactive:
        ap.error('provide queries as positional args, or use --interactive')

    root = resolve_corpus(args.corpus)
    sys.stderr.write(f"[bm25] indexing {root} ...\n")
    idx = CorpusIndex(root, args.include, args.exclude, args.max_file_bytes)
    sys.stderr.write(f"[bm25] indexed {len(idx.docs)} files in {idx.discover_s + idx.index_s:.2f}s "
                     f"(walk {idx.discover_s:.2f}s, index {idx.index_s:.2f}s)\n")
    if args.stats:
        print(json.dumps({'files': len(idx.docs), 'walk_s': round(idx.discover_s, 3),
                          'index_s': round(idx.index_s, 3)}, indent=2))

    for q in args.queries:
        hits = idx.query(q, k=args.top_k)
        print_results(idx, q, hits, args.snippet_lines, args.json)

    if args.interactive:
        sys.stderr.write("[bm25] interactive mode. type query, blank line to exit.\n")
        while True:
            try:
                q = input('bm25> ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q:
                break
            hits = idx.query(q, k=args.top_k)
            print_results(idx, q, hits, args.snippet_lines, args.json)


if __name__ == '__main__':
    main()
