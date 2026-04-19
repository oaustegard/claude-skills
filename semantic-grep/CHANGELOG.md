# semantic-grep - Changelog

All notable changes to the `semantic-grep` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0] - 2026-04-19

### Added

- initial skill: semantic search over text files via `gemini-embedding-001`
- `semantic_grep()` — main search function with `top_k`/`threshold`/`granularity` flags
- `embed_batch()` using Gemini's `:batchEmbedContents` endpoint (1 HTTP call per 100 chunks)
- `load_corpus()` / `chunk_text()` — paragraph or line granularity
- `format_grep()` — grep-compatible `path:line: text [score]` output
- asymmetric `RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT` task types; `code` task mode via `CODE_RETRIEVAL_QUERY`
- MRL truncation (128/768/1536/3072 dims) with client-side renormalization for dims < 3072
- credential loading via `/mnt/project/proxy.env` (CF AI Gateway BYOK) with direct-API fallback

### Notes

- conceptually inspired by [`jina-grep-cli`](https://github.com/jina-ai/jina-grep-cli); swaps MLX backend for Gemini API
- no persistent index yet — every call re-embeds the corpus (serverless mode equivalent)
- embedding function is duplicated here vs `invoking-gemini/scripts/gemini_client.py`; should be factored up when invoking-gemini adds embedding support
