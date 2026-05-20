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

## Caching

The skill maintains a session-local cache at `/home/claude/.bm25-cache/<key>/`.
The key hashes the inputs that determine the index (resolved corpus path,
include/exclude globs, max file size), so any change naturally invalidates.
First invocation against a corpus builds and saves; subsequent invocations
load in ~50ms instead of rebuilding in seconds.

`/home/claude/` is ephemeral, so the cache and the rest of the session
state expire together — no cross-session invalidation problem. Use
`--no-cache` to bypass if you've mutated the corpus mid-session.

## Pairing with other skills

- For code-specific search with regex routing and AST-expanded results,
  use `searching-codebases` instead.
- For symbol lookup (`find:`, `source:`, `refs:`) over a parsed codebase,
  use `tree-sitting` directly.
- bm25 fills the gap between those two and works on non-code corpora
  (project knowledge, transcripts, uploaded docs).
