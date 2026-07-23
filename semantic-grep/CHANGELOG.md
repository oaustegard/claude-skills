# semantic-grep - Changelog

## 2026-07-21

### Changed — default encoder is now `gemini-embedding-2`
- `_DEFAULT_MODEL`: `gemini-embedding-001` → `gemini-embedding-2` (GA 2026-04-22).
- Embedding-2 is a strict superset: same request shape and dims for text, plus
  image and audio into the same vector space. Verified through the CF gateway
  2026-07-21 — 001 rejects non-text input with HTTP 400.

### Retired — `gemini-embedding-001`
- Listed in `_RETIRED_MODELS`; passing it explicitly still works but raises a
  `DeprecationWarning` pointing at the replacement.
- **No migration needed.** This skill is serverless and re-embeds on every call
  (no persistent index), and the memory system stopped generating embeddings in
  v0.13.0 — so no stored 001 vectors exist to invalidate.
- Vectors from different encoders are not comparable; never mix them in one index.

All notable changes to the `semantic-grep` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-07-23

### Fixed

- fall back to env vars for CF gateway credentials (#707)

### Other

- semantic-grep: default to gemini-embedding-2, retire gemini-embedding-001 (#743)

## [0.1.1] - 2026-04-19

### Other

- Add semantic-grep skill (v0.1.0) (#558)

## [0.1.1] - 2026-04-19

### Fixed

- tighten char-per-token ratio (4 → 1.5) so non-ASCII text does not silently overflow Gemini's 2048-token input limit
- `_load_env` now strips `export ` prefix, tolerating shell-sourceable .env files
- `semantic_grep()` raises `ValueError` on empty query instead of hitting the API with empty payload

### Documentation

- SKILL.md clarifies `include` glob matches filename only (not path)
- Limitations section expanded with memory ceiling, symlink-following, and batch bulk-failure notes surfaced by adversarial review

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