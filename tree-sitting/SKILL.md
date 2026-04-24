---
name: tree-sitting
description: AST-powered code navigation via tree-sitter. Auto-scans codebases and provides progressive-disclosure tree views with symbol search, source retrieval, and reference finding. Each invocation is self-contained — no cross-process state. Use when exploring unfamiliar repos, navigating code, or needing fast symbol lookup. Triggers on "map this codebase", "explore repo", "find symbol", "navigate code", "tree-sitter", or when starting work on an unfamiliar repository.
metadata:
  version: 0.5.0
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

### Workflow

```
1. treesit.py /repo                           → orient: what dirs, how big
2. treesit.py /repo --path=src/core           → drill into interesting directory
3. treesit.py /repo 'find:Parser*'            → find specific symbols
4. treesit.py /repo 'source:parse_input'      → read implementation
5. treesit.py /repo 'refs:ParseState'         → find usage across codebase
```

Each call is self-contained. No need to "scan first, query later" —
scan happens automatically every time (~700ms).

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
**Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java, C, HTML, Markdown.**

Three-tier extraction for bundled languages:

1. **Custom extractors** (richest — signatures, hierarchy, docstrings): Python, C, Go, Rust, JavaScript, TypeScript, TSX, Ruby, Markdown (heading outline)
2. **tags.scm queries** (community-maintained — kinds, docs): Java
3. **Generic heuristic** (names + kinds + locations): HTML and any future bundled grammars

### Adding a grammar

Files with unsupported extensions are silently skipped (they show as `SKIP (no parser)` with `--stats`). To add a grammar, drop a compiled `libtree_sitter_<lang>.so` into `parsers/` — the engine picks it up automatically on the next run. Build from the grammar's repo (each `tree-sitter/tree-sitter-<lang>` repo has a `src/` directory you can compile with `cc -shared -fPIC -I src src/parser.c src/scanner.c -o libtree_sitter_<lang>.so`, or use `tree-sitter build`).

If you need a language urgently and can't build the `.so`, you can try installing `tree-sitter-language-pack` as a fallback (`uv pip install --system --break-system-packages tree-sitter-language-pack`) — but note its 1.6.x wheels have a broken install layout in some containers and try to download grammars at runtime from a domain that may not be in your network allowlist. Bundling the `.so` is the reliable path.

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
