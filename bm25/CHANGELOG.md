# Changelog

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
