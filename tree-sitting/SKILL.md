---
name: tree-sitting
description: Symbol-level navigation of a local checkout using tree-sitter ASTs. Answers where a symbol is defined, what lines it spans, which symbols a file exposes, what a directory holds, and where a name is referenced — every answer carries exact line ranges to feed straight into a scoped read. Use for "where is X defined", "who calls X", "find the function/class named", "what's in this file", "give me the line range for", "show me the source of", "list the symbols in", or before editing a file you have not read. Each invocation auto-scans and is self-contained. Not for first-encounter repo orientation (use exploring-codebases), for what a codebase DOES rather than what it contains (featuring), for binding-resolved Python caller sets (searching-codebases), or for literal text and regex matching (plain ripgrep).
metadata:
  version: 0.8.0
---

# tree-sitting

AST-powered code navigation using tree-sitter. Each invocation auto-scans
the codebase (~700ms for 250 files), then runs queries at sub-millisecond speed.

## Setup

```bash
uv pip install --system --break-system-packages tree-sitter
```

Grammars are loaded from bundled `parsers/*.so` files — no network fetch,
no `tree-sitter-language-pack` dependency. Install is <1s.

**Verify the install before trusting an empty result.** Without the
`tree-sitter` core package the CLI parses nothing, prints no error, and exits
0. Run `--stats` on a directory you know contains code; a missing dependency
looks like this:

```
Scanned 0 files (0 KB) in 0ms
Symbols: 0 | Languages:
No files scanned.
```

Zero symbols where you expect code means the dependency is missing, not that
the code is empty. Reinstall and re-run before concluding anything from the
output. There is no `Errors:` line in this case — that line appears only when
a parse fails, and an absent parser never gets that far. Measured 2026-08-24 by
blocking the import and re-running.

## When NOT to use this skill

Reach for the neighbour instead when the task is one of these. Every row is a
skill this one is routinely confused with; a 2026-08-24 retrieval measurement
over the 92-skill pool put tree-sitting outside the top-1 slot on all five of
its own canonical queries, losing them to `accessing-github-repos`,
`featuring`, `searching-codebases` and `cloning-project`.

| Task | Use instead |
|------|-------------|
| The repo is not on local disk yet | `accessing-github-repos`, then come back |
| "What does this repo DO?" — capabilities, not symbols | `featuring` |
| First-encounter orientation on an unfamiliar repo | `exploring-codebases` (it calls this skill in step 2) |
| Teaching a human the codebase through exercises | `orienting-codebases` |
| ALL true callers of a **Python** symbol, binding-resolved | `searching-codebases` (`--refs`; pyright excludes same-named false positives) |
| Ranking files by relevance to a multi-word concept | `bm25` |
| A literal string, regex, or any non-symbol text match | plain `rg` — faster and equally accurate |

Use this skill when the unit of the question is a **symbol or a file's
structure**: where something is defined, what a file exposes, which lines to
read, what a directory contains. `mapping-codebases` is deprecated and points
here; ignore it.

## Usage: CLI (treesit.py)

Every call auto-scans, prints a tree overview, then runs any queries.
No state to manage between calls.

```bash
TREESIT=/mnt/skills/user/tree-sitting/scripts/treesit.py

# Orient: root-level overview (default depth=1)
python3 $TREESIT /path/to/repo

# Featuring: complete tree, minimal detail
python3 $TREESIT /path/to/repo --depth=-1 --detail=sparse

# Explore a subdirectory in full detail
python3 $TREESIT /path/to/repo --path=src/core --detail=full

# Run queries (tree overview + query results)
python3 $TREESIT /path/to/repo 'find:Parser*' 'source:parse_input'

# Queries only, no tree
python3 $TREESIT /path/to/repo --no-tree 'refs:AuthToken'
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--depth N` | 1 | Directory depth: -1=all, 0=root only, 1=one level |
| `--detail LEVEL` | normal | Node detail: sparse, normal, full |
| `--path DIR` | (root) | Scope to subdirectory |
| `--skip DIRS` | | Extra dirs to skip (comma-separated) |
| `--no-tree` | | Suppress tree overview, show only queries |
| `--stats` | | Show scan timing and counts |

### Detail Levels

All levels include line ranges (`:start-end`) so you can feed the
window straight into `Read --offset/--limit` without another scan.

| Level | Tree-overview row (per file) | Use case |
|-------|------------------------------|----------|
| `sparse` | `file: name:1-10, Other:30-90 +3` | featuring: see the full shape |
| `normal` | `file: name(f):1-10, Other(c):30-90 +3` | exploring: quick orientation |
| `full` | full per-symbol formatter + children + imports | exploring: deep dive into a directory |

### Queries

Append after the repo path. Multiple queries per call.

| Query | Example | Description |
|-------|---------|-------------|
| `find:PATTERN[:KIND[:LIMIT]]` | `find:*Handler*:function` | Symbol search (glob/substring) |
| `symbols:FILE` | `symbols:src/api.py` | All symbols in a file |
| `source:SYMBOL[:FILE]` | `source:parse_input` | Source code of a symbol |
| `refs:SYMBOL[:LIMIT]` | `refs:AuthToken:30` | Text references across codebase |
| `imports:FILE` | `imports:src/api.py` | Import list for a file |
| `dir:PATH` | `dir:src/core` | Directory overview (engine format) |

### Caching

Scans are cached to disk, keyed on a fileset fingerprint (mtime + size of all
files under root, combined with skip-set and cache format version). Repeat drills
in a session skip re-parsing — results are byte-identical whether served from
cache or fresh parse.

Cache auto-invalidates when files change, are added, or removed. Use `--no-cache`
to skip cache entirely (always parse), or `--rebuild-cache` to ignore existing
cache and rewrite it. Set `TREESIT_CACHE_DIR` environment variable to relocate
cache from the system temp directory.

### Workflow

For structural drills ("what does this expose", "where is X", "who calls X"),
**batch multiple queries in a single call**:

```bash
# Batch drills (default for exploration)
treesit.py /repo 'find:Parser*' 'source:parse_input' 'refs:ParseState'
```

One scan, all results. Do not fall back to `grep` or `sed` for symbol lookups —
the AST queries (`find:`, `source:`, `refs:`) provide accurate, fast symbol-aware
results that text search cannot match.

For iterative exploration:

```
1. treesit.py /repo                           → orient: what dirs, how big
2. treesit.py /repo --path=src/core           → drill into interesting directory
3. treesit.py /repo 'find:Parser*'            → find specific symbols
4. treesit.py /repo 'source:parse_input'      → read implementation
5. treesit.py /repo 'refs:ParseState'         → find usage across codebase
```

Each call is self-contained. No need to "scan first, query later" —
scan happens automatically, and results are cached for subsequent calls (~700ms first scan).

## Usage: Direct Python (single invocation)

For custom scripts that need the engine API directly:

```python
import sys; sys.path.insert(0, '/mnt/skills/user/tree-sitting/scripts')
from engine import CodeCache

cache = CodeCache()
cache.scan('/path/to/repo')
# All queries in the SAME invocation:
print(cache.tree_overview())
print(cache.find_symbol('ClassName'))
print(cache.get_source_range('src/core/parser.c', 100, 150))
```

**Important:** The cache is in-memory only. All scan + query calls MUST
happen in the same Python process. Splitting across separate `python -c`
invocations loses the cache — use `treesit.py` instead.

## Supported Languages

Bundled grammars (work out of the box):
**Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java, C, HTML, Markdown, Mojo.**

Three-tier extraction for bundled languages:

1. **Custom extractors** (richest — signatures, hierarchy, docstrings): Python, C, Go, Rust, JavaScript, TypeScript, TSX, Ruby, Markdown (heading outline)
2. **tags.scm queries** (community-maintained — kinds, docs): Java, Mojo
3. **Generic heuristic** (names + kinds + locations): HTML and any future bundled grammars

### Adding a grammar

Files with unsupported extensions are silently skipped (they show as `SKIP (no parser)` with `--stats`). To add a grammar, drop a compiled `libtree_sitter_<lang>.so` into `parsers/` — the engine picks it up automatically on the next run. Build from the grammar's repo (each `tree-sitter/tree-sitter-<lang>` repo has a `src/` directory you can compile with `cc -shared -fPIC -I src src/parser.c src/scanner.c -o libtree_sitter_<lang>.so`, or use `tree-sitter build`).

If you need a language urgently and can't build the `.so`, you can try installing `tree-sitter-language-pack` as a fallback (`uv pip install --system --break-system-packages 'tree-sitter-language-pack<1.6.3'`) — but note 1.6.3 ships a broken wheel (only `_native/`, missing the `tree_sitter_language_pack/` python module → `ModuleNotFoundError` despite pip showing it installed); 1.6.2 and earlier work, hence the `<1.6.3` pin and try to download grammars at runtime from a domain that may not be in your network allowlist. Bundling the `.so` is the reliable path.

## What It Extracts

- **Symbols**: functions, classes, structs, enums, methods, constants, defines, types
- **Signatures**: parameter lists and return types (Python, C; partial for others)
- **Doc comments**: first-line summaries from docstrings, JSDoc, Doxygen, `///`, `#`
- **Line ranges**: start and end line for every symbol
- **Imports**: per-file dependency tracking
- **Hierarchy**: class→methods, struct→fields (Python, C)

## Architecture

```
CodeCache (in-memory, per-invocation)
  ├── files: {relpath → FileEntry(source, tree, symbols, imports)}
  ├── _symbol_index: {name → [Symbol, ...]}  ← fast lookup
  └── methods: scan(), find_symbol(), file_symbols(), dir_overview(), ...
       │
       └── treesit.py CLI — auto-scan + progressive-disclosure tree + queries
```

Parse cost is paid once per invocation. The symbol index enables O(1) exact
match and O(n) substring/glob search where n is the number of unique symbol
names (not files).
