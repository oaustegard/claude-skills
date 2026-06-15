---
name: searching-codebases
description: >-
  Find code by regex pattern or natural language concept in any codebase.
  Auto-routes between n-gram indexed regex search (2-20x faster than ripgrep)
  and TF-IDF semantic search. Expands results to full functions via tree-sitting
  AST data. Accepts GitHub URLs, local directories, uploaded files/archives, or
  project knowledge. Use when asked to find implementations, search for patterns,
  or answer "where is X" / "how does Y work" about code. Triggers on "search
  this repo", "find where X is", "grep for", "what handles Y", regex patterns,
  or natural-language questions about code. This is the convergent "find X" skill
  — for first-encounter orientation, use exploring-codebases instead. For Python
  sources, a binding-resolved reference/definition tier (pyright, via python-lsp)
  is available with --refs/--def/--hover.
metadata:
  version: 2.1.0
---

# Searching Codebases

Find code in any codebase by pattern or concept. One entry point, two
search strategies, automatic routing.

## Prerequisites

```bash
uv tool install ripgrep
```

tree-sitting (for structural context expansion) installs automatically when
the `--expand` flag is used.

## Primary Command

```bash
SKILL_DIR=/mnt/skills/user/searching-codebases

python3 $SKILL_DIR/scripts/search.py SOURCE "query1" ["query2" ...] [OPTIONS]
```

SOURCE is any of:
- Local directory path
- GitHub URL (downloads tarball automatically)
- `uploads` (uses `/mnt/user-data/uploads/`)
- `project` (uses `/mnt/project/`)
- Path to a `.zip` or `.tar.gz` archive

## Search Modes

**Regex mode** (patterns, identifiers, literal text):
```bash
python3 $SKILL_DIR/scripts/search.py ./repo "def handle_error"
python3 $SKILL_DIR/scripts/search.py ./repo "class.*Exception" --regex
python3 $SKILL_DIR/scripts/search.py ./repo "TODO|FIXME|HACK"
```

**Semantic mode** (concepts, natural language):
```bash
python3 $SKILL_DIR/scripts/search.py ./repo "retry logic with backoff" --semantic
python3 $SKILL_DIR/scripts/search.py ./repo "authentication flow"
python3 $SKILL_DIR/scripts/search.py ./repo "error handling strategy"
```

Auto-detection: short queries and code-like tokens → regex. Multi-word
natural language → semantic. Override with `--regex` or `--semantic`.

**Binding-resolved mode** (Python only — pyright via the `python-lsp` skill):
```bash
python3 $SKILL_DIR/scripts/search.py ./repo --refs SYMBOL    # find all real uses
python3 $SKILL_DIR/scripts/search.py ./repo --def SYMBOL     # go-to-definition
python3 $SKILL_DIR/scripts/search.py ./repo --hover SYMBOL   # inferred type/signature
```

Regex mode matches *text*, so a cross-reference for a function false-positives
on shadowed and same-named-but-unrelated symbols. `--refs` is **binding-resolved**:
pyright excludes the unrelated same-named symbol and follows imports. Use it when
you need a true "find all callers/users" for a `.py` symbol, not a text grep.

The tier is engaged **lazily** — pyright's index cost is paid only when you ask
for `--refs`/`--def`/`--hover`, never on ordinary searches. It is **Python-only**;
for non-`.py` sources, or when pyright/node is unavailable, it prints a one-line
degradation note and falls back to the regex text path. Each takes a single bare
symbol name and is mutually exclusive with the other two and with text queries.

## Options

- `--regex` / `--semantic`: Force search mode
- `--refs SYMBOL` / `--def SYMBOL` / `--hover SYMBOL`: Binding-resolved Python
  queries via pyright (see Binding-resolved mode above)
- `--expand`: Return full function bodies via tree-sitting AST context
- `--benchmark`: Compare indexed regex vs brute-force ripgrep
- `--branch NAME`: Git branch for GitHub URLs (default: main)
- `--skip DIRS`: Comma-separated directories to skip
- `--json`: Machine-readable output
- `-v`: Show index stats and query routing decisions

## How It Works

**Regex search** builds a sparse n-gram inverted index over all files.
Queries are decomposed into literal fragments, looked up in the index
to identify candidate files (typically 90-99% reduction), then verified
with ripgrep. Frequency-weighted n-grams make rare character sequences
more selective.

**Semantic search** builds a TF-IDF index over code chunks (functions,
classes, structural entries). Queries are ranked by cosine similarity.

**Context expansion** (`--expand`) uses tree-sitting's AST cache to
identify function/class boundaries, returning complete structural units
rather than line fragments. On first use, tree-sitting scans the repo
(~700ms for 250 files); subsequent expansions are sub-millisecond.

**Small codebases** (< 20 files) skip indexing entirely — direct ripgrep is
faster when there's nothing to narrow.

## Mixed Queries

Multiple queries can use different modes in a single invocation. Each query
is auto-routed independently, and indexes are built once per mode:

```bash
python3 $SKILL_DIR/scripts/search.py ./repo \
  "class.*Error" \
  "error recovery strategy" \
  "def retry"
```

## Dependencies

- **tree-sitting**: Provides AST-based context expansion for `--expand`.
  Not required — search works without it, just with less structural context
  in results.
- **ripgrep**: Required for regex verification. Install via `uv tool install ripgrep`.
- **scikit-learn**: Required for semantic mode. Installs automatically.
- **python-lsp**: Provides the binding-resolved tier (`--refs`/`--def`/`--hover`).
  Self-bootstraps pyright on first use and requires system `node` (v18+). Not
  required — without it those flags degrade to the regex text path.

## When to Use

- **Known target**: "where is the retry logic?", "find all error handlers"
- **Pattern matching**: regex across large codebases with indexed speedup
- **Concept search**: "authentication flow", "database connection pooling"
- **Cross-reference**: find all callers/users of a specific function — for
  `.py` symbols use `--refs` (binding-resolved, no same-name false positives)

## When NOT to Use

- **First encounter**: "what does this repo do?" → use exploring-codebases
- **Repos under ~10 files**: just read them directly
- **Exact symbol lookup**: `find_symbol('ClassName')` via tree-sitting is simpler
- **Structural overview**: use tree-sitting's `tree_overview()` / `dir_overview()`

## Files

- `scripts/search.py` — Entry point, query routing, output formatting
- `scripts/resolve.py` — Input source resolution (GitHub, uploads, archives)
- `scripts/context.py` — tree-sitting-based AST context expansion
- `scripts/ngram_index.py` — Sparse n-gram inverted index, regex decomposition
- `scripts/sparse_ngrams.py` — Core n-gram algorithms, frequency weights
- `scripts/code_rag.py` — TF-IDF semantic search over code chunks
- `scripts/lsp_refs.py` — Binding-resolved Python tier: symbol→position
  resolution (tree-sitting), pyright queries (python-lsp), soft fallback
