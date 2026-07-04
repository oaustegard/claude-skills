---
name: searching-codebases
description: >-
  Binding-resolved Python symbol queries — find all true callers (--refs),
  go-to-definition (--def), or inferred signature (--hover) of a .py symbol
  via pyright, excluding same-named false positives that text grep cannot.
  Use when a task needs ALL callers/users of a Python symbol or its real
  definition and text matching would over-match. For everything else —
  literal tokens, regex patterns, concept/natural-language search, any repo
  size — plain ripgrep is faster and equally accurate: measured 2026-07-04
  on real issue-localization tasks, the semantic and indexed-regex tiers
  tied or lost against naive rg at 4-60x the wall-clock cost. Those tiers
  remain available below but are NOT recommended as a default.
metadata:
  version: 2.2.0
---

# Searching Codebases

Find code in any codebase by pattern or concept. One entry point, two
search strategies, automatic routing.

## Prerequisites

```bash
uv tool install ripgrep
```

tree-sitting installs automatically when needed — for `--expand` context
expansion and for the binding-resolved `--refs`/`--def`/`--hover` tier, which
uses it to resolve symbol positions. Only the bare `tree-sitter` package is
fetched; the language grammars ship bundled.

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

- **tree-sitting**: Provides AST context expansion for `--expand` *and* the
  symbol→position resolution that seeds the binding-resolved tier
  (`--refs`/`--def`/`--hover`). Auto-installs the bare `tree-sitter` package
  when either is used (grammars are bundled). Regex and semantic search work
  without it.
- **ripgrep**: Required for regex verification. Install via `uv tool install ripgrep`.
- **scikit-learn**: Required for semantic mode. Installs automatically.
- **python-lsp**: Provides the binding-resolved tier (`--refs`/`--def`/`--hover`).
  Self-bootstraps pyright on first use and requires system `node` (v18+). Not
  required — without it those flags degrade to the regex text path.

## When to Use — narrow, by design

The ONE recommended use: **binding-resolved Python symbol queries**.

- "find all callers of `X`" / "where is `X` really defined" for a `.py`
  symbol, when same-named-but-unrelated symbols would pollute a text grep.
  Empirical basis: `rg get` on psf/requests returned 232 hits, 224 of them
  false; `--refs get` excluded all 224 (2026-06-15).

## When NOT to Use — which is most of the time

Everything else. Measured head-to-head on real issue-localization tasks
(7 scikit-learn issues with merged fix-PRs, gold = PR diff files,
2026-07-04, replicating the file-discovery metric of arXiv:2602.11988):

- **Literal tokens / identifiers**: naive `rg -l` tied or beat the indexed
  tier on recall@10 in every instance, at 0.4s vs 25s.
- **Concept / natural-language search**: the TF-IDF semantic tier never
  beat identifier grep — not even on identifier-poor issues, which are
  themselves rare (~0.3% of merged-PR traffic in the sample).
- **First encounter / "what is this repo"**: use exploring-codebases.
- **Repos under ~20 files**: read them.

The self-test before invoking: would plain `rg` return the same answer?
If yes, use rg. The indexed-regex and semantic tiers are retained for
completeness and for corpora where they may yet earn their cost (very
large repos, non-code document collections), but they carry the burden
of proof.

## Files

- `scripts/search.py` — Entry point, query routing, output formatting
- `scripts/resolve.py` — Input source resolution (GitHub, uploads, archives)
- `scripts/context.py` — tree-sitting-based AST context expansion
- `scripts/ngram_index.py` — Sparse n-gram inverted index, regex decomposition
- `scripts/sparse_ngrams.py` — Core n-gram algorithms, frequency weights
- `scripts/code_rag.py` — TF-IDF semantic search over code chunks
- `scripts/lsp_refs.py` — Binding-resolved Python tier: symbol→position
  resolution (tree-sitting), pyright queries (python-lsp), soft fallback
