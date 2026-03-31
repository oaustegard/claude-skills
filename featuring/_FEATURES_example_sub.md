# Features: Memory Operations

← [Root features](../_FEATURES.md)

> The core memory pipeline: storing observations, querying them back with flexible filters, evolving memories over time, and keeping the store healthy as it grows.

## Memory Storage

Store observations, facts, decisions, and experiences that persist across conversations. Each memory has a type (world, decision, analysis, etc.), tags for retrieval, a confidence score, and a priority that affects ranking.

**Key symbols:**
- `scripts/memory.py#remember` — Primary storage entry point. Validates type, generates embedding-ready summary, writes to Turso.
- `scripts/memory.py#remember_batch` — Bulk storage in a single HTTP round-trip for multi-memory operations.

**Workflow:** Caller provides a summary string, a type, and optional tags/refs/priority. The function generates a UUID, timestamps it, writes to the memories table with FTS5 indexing, and returns the ID. Background mode defers the write to a thread.

**Constraints:** Type is required (enforced, not defaulted). Priority defaults to 0; range is -1 to 2. Confidence defaults to 0.9 if omitted.

---

## Memory Retrieval

Query stored memories by text search, tags, type, time range, or combination. BM25 full-text search handles fuzzy matching; tag filtering supports any/all modes.

**Key symbols:**
- `scripts/memory.py#recall` — Primary query interface with flexible filters (search, tags, type, time, session).
- `scripts/memory.py#recall_batch` — Execute multiple search queries in a single HTTP round-trip.
- `scripts/memory.py#recall_since` — Time-windowed retrieval for recent memories.
- `scripts/hints.py#recall_hints` — Proactive memory surfacing based on context terms.
- `scripts/result.py#MemoryResult` — Type-safe wrapper providing attribute access and field validation.

**Workflow:** `recall("search terms", tags=["topic"], n=10)` queries FTS5 with BM25 ranking, applies tag/type/confidence filters, orders by composite score (BM25 × priority weight), and returns `MemoryResultList`.

**Constraints:** Parameter is `n=` not `limit=`. Tag mode defaults to "any" (OR). Strict mode raises on empty results.

---

## Memory Lifecycle

Evolve memories over time: soft-delete, supersede with updated versions, adjust priority up or down.

**Key symbols:**
- `scripts/memory.py#forget` — Soft-delete by full or partial UUID.
- `scripts/memory.py#supersede` — Replace a memory with an updated version, preserving lineage via refs.
- `scripts/memory.py#reprioritize` — Adjust priority directly.
- `scripts/memory.py#strengthen` — Increment priority (used during therapy and reinforcement).
- `scripts/memory.py#weaken` — Decrement priority.

**Workflow:** `supersede(old_id, new_summary, type)` creates a new memory with a ref pointing to the original, then soft-deletes the original. The chain is traversable via `get_chain()`.

---

## Memory Maintenance

Autonomous curation, consolidation, and pruning to keep the memory store healthy as it grows.

**Key symbols:**
- `scripts/memory.py#consolidate` — Cluster related memories by tag overlap and merge into summary memories.
- `scripts/memory.py#curate` — Autonomous pipeline: detect duplicates, stale memories, consolidation opportunities.
- `scripts/memory.py#prune_by_age` — Remove old low-priority memories (dry_run by default).
- `scripts/memory.py#memory_histogram` — Distribution of memories by type, priority, and age for diagnostics.

**Constraints:** All destructive operations default to `dry_run=True`. Consolidation requires `min_cluster=3` memories to trigger.

---

## Decision Tracing

Structured capture of decisions with context, rationale, alternatives, and trade-offs. Enables post-hoc review of why choices were made.

**Key symbols:**
- `scripts/memory.py#decision_trace` — Store a formatted decision with choice/context/rationale/alternatives.
- `scripts/memory.py#get_alternatives` — Extract rejected alternatives from a decision's refs.
- `scripts/memory.py#get_chain` — Follow reference chains to build a context graph around a memory.

**Workflow:** `decision_trace(choice, context, rationale, alternatives=[...])` creates a decision-type memory with standardized format and "decision-trace" tag. Later, `get_chain()` traverses refs to reconstruct the decision graph.
