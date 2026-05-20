# Changelog

## 0.1.2 — 2026-05-18

Added a session-local disk cache at `/home/claude/.bm25-cache/<key>/`. Across `bash_tool` invocations the in-memory retriever evaporates at process exit, so repeat queries against the same corpus would otherwise rebuild from scratch. The cache key hashes the resolved corpus path plus the include/exclude globs plus max-file-bytes, so any input change invalidates naturally. Verified on Django (1,962 files): 1.5s rebuild → 40ms load. `--no-cache` bypasses both load and save for the rare "I mutated the corpus mid-session" case.

The cache lives in `/home/claude/`, which is ephemeral, so it expires at the session boundary — same lifetime as the corpus state itself, no cross-session staleness problem.

## 0.1.1 — 2026-05-18

Setup uses `uv pip install --system --break-system-packages bm25s` instead of plain pip. Matches the convention across sibling skills (tree-sitting, container-layer, etc.); sub-second install on a warm uv cache. Updated SKILL.md, README, and the script's missing-dependency error message accordingly. No behavior change.

## 0.1.0 — 2026-05-18

Initial release. Stateless BM25 search wrapper around xhluca/bm25s.

- CLI `bm25.py` with corpus types: local dir, `uploads`, `project`, `github.com/owner/repo[@ref]`
- Filters: `--include`, `--exclude` (glob), `--max-file-bytes`
- Output: human-readable with snippet context (`--snippet-lines`), or `--json`
- `--interactive` REPL for ad-hoc querying within one session
- Default text-extension allowlist; standard noise dirs (`.git`, `node_modules`, `__pycache__`, etc.) always skipped
- No persistence — every invocation rebuilds. See README for rationale.

Empirical basis: [Fly 2026-05-18 — Where AST Helps BM25 (and Where It Doesn't)](https://muninn.austegard.com/perch/fly-2026-05-18-where-ast-helps-bm25-and-where-it-doesnt.html). Token-stream filtering was tested on a Django sample and gave near-identical rankings to plain text indexing, so it isn't worth the complexity in v0.1.

## [0.1.0] - 2026-05-20

### Other

- Add bm25 skill: stateless BM25 search over any corpus
