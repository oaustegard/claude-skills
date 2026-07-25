---
name: bm25
description: >-
  Ranked content search over any text corpus using BM25 (via xhluca/bm25s).
  Corpus-agnostic: works on cloned repos, project knowledge stores, uploaded
  files/archives, and any local directory. Stateless — builds an in-memory
  index each invocation, no cache, no persistence. Use when you need ranked
  multi-word content search beyond grep, or when picking the "most relevant
  files for these terms" across a corpus. Triggers on "rank these documents",
  "search this corpus", "find content about X", "which files are most about
  Y", or multi-word concept queries against a known body of text.
metadata:
  version: 0.1.2
---

# bm25

Ranked content search over any text corpus. One CLI, in-memory BM25 index
per process, with a session-local disk cache so repeat invocations against
the same corpus load in tens of milliseconds instead of rebuilding.

## Setup

```bash
uv pip install --system --break-system-packages bm25s
```

Install is sub-second on a warm uv cache. That's the entire dependency.

## Usage

```bash
BM25=/mnt/skills/user/bm25/scripts/bm25.py

# Local directory
python3 $BM25 ./repo 'csrf middleware'

# Multiple queries against the same in-memory index (build once, query many)
python3 $BM25 ./repo 'csrf middleware' 'session backend' 'queryset filter'

# Cloned GitHub repo via tarball (one HTTP call)
python3 $BM25 'github.com/django/django' 'atomic transaction'
python3 $BM25 'github.com/django/django@stable/5.0.x' 'atomic transaction'

# Project knowledge or uploads
python3 $BM25 project 'RAG scaling laws'
python3 $BM25 uploads 'tax loss harvesting'

# Filters
python3 $BM25 ./repo 'auth flow' --exclude 'tests/*' --exclude '*/tests/*'
python3 $BM25 ./repo 'config' --include '*.py' --include '*.toml'

# Interactive (REPL — single corpus, many queries)
python3 $BM25 ./repo --interactive

# JSON output for piping
python3 $BM25 ./repo 'auth flow' --json
```

## Corpus types

| Spec | Meaning |
|------|---------|
| `./path` or `/abs/path` | Local directory |
| `uploads` | `/mnt/user-data/uploads/` |
| `project` | `/mnt/project/` |
| `github.com/owner/repo[@ref]` | Tarball fetch via GitHub API (`GH_TOKEN` used if set) |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--top-k N` | 10 | Results per query |
| `--include GLOB` | (auto) | Repeatable. If set, only files matching one of these globs are indexed |
| `--exclude GLOB` | | Repeatable. Skip files matching these globs |
| `--snippet-lines N` | 3 | Lines of snippet context per hit (0 = none) |
| `--max-file-bytes N` | 2,000,000 | Skip files larger than this |
| `--json` | | Machine-readable output |
| `--interactive` / `-i` | | REPL mode for ad-hoc querying within one session |
| `--stats` | | Print discover + index timings as JSON |
| `--no-cache` | | Bypass the session-local index cache; build in-memory only |

With no `--include`, a default set of text/code extensions is indexed (Python,
JS/TS, Go, Rust, Markdown, JSON, YAML, etc.). Standard noise dirs are skipped
unconditionally: `.git`, `node_modules`, `__pycache__`, `.venv`, `dist`, etc.

## When to use bm25

| Question shape | Tool |
|----------------|------|
| "Find lines matching `class.*Error`" | `grep` / ripgrep |
| "Show me where `parse_input` is defined" | `tree-sitting` (`find:`/`source:`) |
| "Which files are about CSRF handling?" | **bm25** |
| "Rank these docs by relevance to 'rate limiting strategies'" | **bm25** |
| "What's the implementation of the atomic transaction context manager?" | **bm25**, then `tree-sitting source:` |
| "Find code by natural-language concept (in a code repo)" | `searching-codebases` (which has its own TF-IDF mode) |

The boundary with `searching-codebases`: that skill is code-specific (routes
between regex and TF-IDF, expands via tree-sitting AST). `bm25` is the simpler
general-purpose tool — any corpus, no AST awareness, no routing. Prefer
`searching-codebases` for code; reach for `bm25` when the corpus is mixed
(docs + code), non-code (notes, transcripts, PDFs converted to text), or when
you specifically want BM25's length-normalized scoring.

## Design notes

- **Session-local disk cache** at `/home/claude/.bm25-cache/<key>/`. The
  key is a hash of `(resolved_corpus_path, include_globs, exclude_globs,
  max_file_bytes)` — any change invalidates naturally. First invocation
  builds and saves; subsequent invocations against the same corpus and
  filters load in tens of milliseconds. The cache lives in `/home/claude`,
  which is ephemeral, so it expires at the session boundary — same
  lifetime as the corpus state itself, no cross-session staleness.
  ~5–35MB per cached index, depending on corpus size.
- **`--no-cache`** bypasses both load and save — useful only if you've
  mutated the corpus mid-session (rare) or want to confirm a rebuild matches.
- **Reuse within a single invocation.** The retriever stays in memory
  between queries in one process. Passing multiple queries positionally,
  or using `--interactive`, amortizes any rebuild cost across queries.
- **No AST awareness.** Chunking is per-file. For symbol-level results in
  code, combine with `tree-sitting` queries on the same paths.
- **Tokenizer.** Default `bm25s.tokenize` with stopwords disabled — over a
  small Django sample, AST-derived token streams (identifiers/strings/
  comments only) gave near-identical rankings, so we don't bother.

## Output format

Default (human-readable):

```
QUERY: csrf middleware
----------------------------------------------------------------------
  1.   5.51  django/core/checks/security/csrf.py
    def _csrf_middleware():
        return "django.middleware.csrf.CsrfViewMiddleware" in settings.MIDDLEWARE
  2.   5.34  docs/howto/csrf.txt
    ...
```

`--json` produces `{"query": ..., "results": [{"path", "score", "snippet"}, ...]}`.

## Architecture

```
bm25.py CLI
  ├── resolve_corpus(spec)         → local Path (downloads tarball if github.com/...)
  ├── cache_key(...)               → 16-hex sha256 of inputs that determine the index
  ├── CorpusIndex.load(cache_dir)  → returns cached index if present, else None
  ├── CorpusIndex.build(...)       → walks files, tokenizes, indexes with bm25s
  ├── CorpusIndex.save(cache_dir)  → persists to /home/claude/.bm25-cache/<key>/
  ├── query(q, k)                  → ranked (doc_idx, score) pairs
  └── best_snippet(doc, q, lines)  → pick line w/ most query-term hits + context
```

Cache contents per directory:
- `bm25/` — bm25s.BM25.save() output (NumPy arrays + vocab)
- `corpus.pkl` — pickled `{paths, docs}` so we can render snippets without
  re-reading the source files
- `manifest.json` — corpus root, files count, built_at timestamp

No network beyond optional tarball fetch on `github.com/...` corpora. No
state outside `/home/claude/`, which is ephemeral.
