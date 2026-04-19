---
name: semantic-grep
description: In-process semantic search over text files or in-memory strings, using Gemini embeddings via the CF AI Gateway. Use when user wants fuzzy/conceptual search where exact-keyword grep would miss — "sessions discussing regulatory constraints", "code about retry logic", "notes mentioning burnout even if the word isn't there". Complements searching-codebases (regex/AST) and extracting-keywords (YAKE). Do NOT use when an exact string/regex match is what's wanted — grep/rg wins on speed and precision there.
metadata:
  version: 0.1.1
---

# Semantic Grep

jina-grep-style semantic search, done in-process via Python rather than as an external CLI. Embeds query + corpus chunks with `gemini-embedding-001`, ranks by cosine similarity, returns grep-format output.

## When Semantic Search Helps

The core trade-off (lifted from `jina-grep-cli`'s own docs and validated in testing):

| Task | Tool |
|------|------|
| Known exact string, filename, or regex | `grep` / `rg` / `searching-codebases` |
| "What files discuss concept X" when X may not appear verbatim | **semantic-grep** |
| Hybrid: prefilter with grep, rerank by concept | grep → `rerank_candidates()` |

**Regression test result (workshop session corpus, 135 docs):**
- *"handling regulatory constraints"* → top hit *"Engineering AI Systems Under Sovereignty Constraints"* (0.67). ✓
- *"sessions about GEPA"* → top hit *"Gemma, DeepMind's Family of Open Models"* (0.69). ✗ — false positive on phonetic neighbor. GEPA is mentioned verbatim in one session description; grep would find it correctly.

**Rule: when the user query reads like a named entity or keyword, try grep first. Only reach for semantic-grep when paraphrase/concept matching is actually needed.**

## Setup

Credentials via `proxy.env` (Cloudflare AI Gateway w/ BYOK — same pattern as `invoking-gemini`):

```
CF_ACCOUNT_ID=...
CF_GATEWAY_ID=...
CF_API_TOKEN=...
```

Direct-API fallback: `GOOGLE_API_KEY` or `GEMINI_API_KEY` env var. No dependencies beyond `requests` + `numpy`.

## Quick Start

```python
import sys
sys.path.insert(0, '/mnt/skills/user/semantic-grep/scripts')
from semantic_grep import semantic_grep, format_grep

# Directory of .txt files
results = semantic_grep("error handling under load", "/path/to/notes",
                        top_k=5, granularity="paragraph")
print(format_grep(results))
# notes/incidents.txt:42:  When the queue depth exceeds... [0.71]
# notes/postmortem.txt:8:  Under sustained traffic we saw... [0.68]
```

## Core API

### `semantic_grep(query, corpus, *, top_k=10, threshold=None, ...)`

Main search function.

- `query` *(str)* — the search query (embedded with `RETRIEVAL_QUERY` task type)
- `corpus` *(str | Path | list[Chunk])* — a file, directory, or pre-chunked list
- `top_k` *(int | None)* — max results; `None` = all above threshold
- `threshold` *(float | None)* — cosine similarity cutoff; `None` = no filter (top_k only)
- `granularity` *("paragraph" | "line")* — how to chunk files (default paragraph)
- `include` *(str)* — filename-glob filter when `corpus` is a directory (default `"*.txt"`). Matches against `Path.name` only, not the full path — `"*.md"` works, `"docs/*.md"` does not.
- `model` *(str)* — default `"gemini-embedding-001"`
- `dim` *(int)* — 128 / 768 / 1536 / 3072 (default 768; MRL-truncated + renormalized)
- `task` *("text" | "code")* — selects text vs code task types

Returns `list[Match]` where `Match` has `path`, `line`, `text`, `score`.

### `load_corpus(path, *, include="*.txt", granularity="paragraph") -> list[Chunk]`

Load and chunk a file or directory without embedding. Useful for inspecting what gets embedded before paying for the API call.

### `embed_batch(texts, task_type, *, model, dim, group_size=100) -> np.ndarray`

Lower-level: embed a list of strings directly via `:batchEmbedContents`. Returns `(N, dim)` float32 array, rows normalized when `dim < 3072`.

### `format_grep(matches, *, max_text_chars=200, show_score=True) -> str`

Format matches as grep output: `path:line: snippet  [score]`.

## Pipe-mode Rerank Pattern

The highest-leverage use isn't naive full-corpus semantic search — it's hybrid retrieval: **fast coarse filter → semantic rerank**.

```python
import subprocess
from semantic_grep import Chunk, semantic_grep, format_grep

# Stage 1: fast exact/regex prefilter with rg
result = subprocess.run(
    ["rg", "-n", "--no-heading", "error|fail|timeout", "logs/"],
    capture_output=True, text=True,
)

# Parse `path:line:text` into Chunks
chunks = []
for raw in result.stdout.splitlines():
    path, line, text = raw.split(":", 2)
    chunks.append(Chunk(path=path, line=int(line), text=text))

# Stage 2: semantic rerank on the prefiltered subset
ranked = semantic_grep("intermittent queue saturation during peak traffic",
                       chunks, top_k=10)
print(format_grep(ranked))
```

This is how you scale past the "embed the whole corpus every call" limit without needing a vector DB. The exact-match stage cheaply cuts millions of lines to thousands; semantic reranks those.

## Task Types (Gemini)

- **text mode** (default): query → `RETRIEVAL_QUERY`, docs → `RETRIEVAL_DOCUMENT`. Asymmetric — documented to outperform symmetric encoding for retrieval.
- **code mode**: query → `CODE_RETRIEVAL_QUERY`, docs → `RETRIEVAL_DOCUMENT`. Use when searching code with natural-language queries.

Use `SEMANTIC_SIMILARITY` (symmetric) only if you're doing pairwise sim, not retrieval. This module doesn't expose that path yet.

## Model Notes

`gemini-embedding-001` (GA since Feb 2026):
- 2,048 input token limit per text. Longer texts are truncated at ~8K chars (approximation).
- Matryoshka (MRL) — 3072 native dims, safely truncatable to 1536/768/256/128.
- 3072 is auto-normalized; lower dims need client-side renorm (handled here).
- Pricing: $0.15 / 1M input tokens. 135 medium paragraphs ≈ 15K tokens ≈ $0.002 per query.

`gemini-embedding-2-preview` (March 2026) is multimodal and currently top of MTEB. Set `model="gemini-embedding-2-preview"` to opt in once the preview stabilizes.

## Limitations (v0.1.1)

- **No persistent index.** Every call re-embeds the corpus. Fine for <~1K chunks; prohibitive for real knowledge bases. Phase 2: cache embeddings by content hash.
- **Token budget is approximated by char count (×1.5).** Conservative for mixed-script text; over-truncates English slightly. Real tokenizer would use the Gemini tokenizer endpoint but costs an extra call per embed.
- **Batch bulk-failure diagnostic.** If one text in a group of 100 overflows or is rejected by safety filters, the whole batch fails and the 99 good ones are lost. No per-index fallback yet.
- **No memory ceiling on corpus size.** `semantic_grep` pre-allocates `(N, dim)` float32; 1M chunks at dim=768 ≈ 3GB. Caller is responsible for sane chunk counts. `load_corpus` also follows symlinks via `rglob` — fine in a trusted single-user container, not for untrusted paths.
- **Sequential batch groups.** `group_size=100` per HTTP call; groups run serially. For >1K chunks, add asyncio — not needed yet.
- **No CLI shim.** Called as a Python module, not a subprocess. Per design: "within an LLM rather than calling out to one."
- **Embedding function lives here, not in `invoking-gemini`.** Should be factored up when invoking-gemini adds embedding support. Tracked as followup.

## Related Skills

- `invoking-gemini` — sibling; handles Gemini text + image generation through the same CF gateway. Shares credential pattern.
- `searching-codebases` — regex/AST search. Use first when the query is a known pattern.
- `extracting-keywords` — YAKE keyword extraction; orthogonal, but pairs well for building query terms from a long prompt.
- `exploring-codebases` — for understanding repo structure. Semantic-grep doesn't replace AST-based navigation.

## Attribution

Conceptually inspired by [`jina-grep-cli`](https://github.com/jina-ai/jina-grep-cli) — we kept the retrieval shape (grep-compatible output, asymmetric query/doc embeddings, threshold + top-k) but swapped the MLX/Apple-Silicon backend for a portable Gemini API call. The original's pipe-mode rerank pattern is the most generalizable idea it contributes and is preserved here.
