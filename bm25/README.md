# bm25

Stateless BM25 content search over any text corpus. Wraps
[xhluca/bm25s](https://github.com/xhluca/bm25s) in a small CLI.

See `SKILL.md` for the full reference.

## Quick start

```bash
uv pip install --system --break-system-packages bm25s

BM25=/mnt/skills/user/bm25/scripts/bm25.py

python3 $BM25 ./repo 'csrf middleware'
python3 $BM25 'github.com/django/django' 'atomic transaction'
python3 $BM25 project 'RAG scaling laws'
```

## Why stateless

Index builds are fast — Django (2,909 .py files) indexes in ~8 seconds,
small repos in well under a second. Caching the index would cost more in
invalidation logic than it saves. Within a single invocation, the index
is held in memory, so passing multiple queries on the command line (or
using `--interactive`) amortizes the build cost across queries.

## Pairing with other skills

- For code-specific search with regex routing and AST-expanded results,
  use `searching-codebases` instead.
- For symbol lookup (`find:`, `source:`, `refs:`) over a parsed codebase,
  use `tree-sitting` directly.
- bm25 fills the gap between those two and works on non-code corpora
  (project knowledge, transcripts, uploaded docs).
