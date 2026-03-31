# Features: remembering

> Persistent memory system for an AI agent (Muninn). Stores typed, tagged, prioritized memories in a Turso database with BM25 full-text search, and loads identity/operational config at conversation start.

## Memory Storage

Store observations, facts, decisions, and experiences that persist across conversations. Each memory has a type (world, decision, analysis, etc.), tags for retrieval, a confidence score, and a priority that affects ranking.

**Key symbols:**
- `scripts/memory.py#remember` — Primary storage entry point. Validates type, generates embedding-ready summary, writes to Turso.
- `scripts/memory.py#remember_batch` — Bulk storage in a single HTTP round-trip for multi-memory operations.
- `scripts/memory.py#remember_bg` — Deprecated async variant; use `remember(..., sync=False)` instead.
- `scripts/memory.py#flush` — Block until pending background writes complete.

**Workflow:** Caller provides a summary string, a type, and optional tags/refs/priority. The function generates a UUID, timestamps it, writes to the memories table with FTS5 indexing, and returns the ID. Background mode defers the write to a thread.

**Constraints:** Type is required (enforced, not defaulted). Priority defaults to 0; range is -1 to 2. Confidence defaults to 0.9 if omitted.

---

## Memory Retrieval

Query stored memories by text search, tags, type, time range, or combination. BM25 full-text search handles fuzzy matching; tag filtering supports any/all modes.

**Key symbols:**
- `scripts/memory.py#recall` — Primary query interface with flexible filters (search, tags, type, time, session).
- `scripts/memory.py#recall_batch` — Execute multiple search queries in a single HTTP round-trip.
- `scripts/memory.py#recall_since` — Time-windowed retrieval for recent memories.
- `scripts/memory.py#recall_between` — Retrieval within a specific time range.
- `scripts/hints.py#recall_hints` — Proactive memory surfacing based on context terms.
- `scripts/result.py#MemoryResult` — Type-safe wrapper providing attribute access, field validation, and alias resolution for query results.
- `scripts/result.py#MemoryResultList` — List wrapper for batch results.

**Workflow:** `recall("search terms", tags=["topic"], n=10)` queries FTS5 with BM25 ranking, applies tag/type/confidence filters, orders by composite score (BM25 × priority weight), and returns `MemoryResultList`. Results expose `.summary`, `.tags`, `.priority`, `.valid_from` etc. via `MemoryResult`.

**Constraints:** Parameter is `n=` not `limit=`. Returns list of dicts wrapped in MemoryResult. Tag mode defaults to "any" (OR). Strict mode raises on empty results.

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
- `scripts/memory.py#prune_by_priority` — Remove memories below a priority threshold.
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

---

## Configuration

Two-table architecture: `config` stores boot-loaded identity and operational settings; `memories` stores searchable observations. Config entries have categories (profile, ops, journal), boot_load flags, and priority for ordering.

**Key symbols:**
- `scripts/config.py#config_get` — Retrieve a config value by key.
- `scripts/config.py#config_set` — Store a config value with category, optional char limit, and read-only flag.
- `scripts/config.py#config_delete` — Remove a config entry.
- `scripts/config.py#config_list` — List entries, optionally filtered by category.
- `scripts/config.py#config_set_boot_load` — Toggle whether a config entry loads at boot.
- `scripts/config.py#config_set_priority` — Set ordering priority within a category.

**Constraints:** Categories are: profile, ops, journal. Boot_load controls whether an entry appears in the boot context window.

---

## Boot Sequence

Load identity (profile) and operational instructions (ops) from the config table at conversation start. Groups ops entries by cognitive domain for organized output.

**Key symbols:**
- `scripts/boot.py#boot` — Main entry point. Loads profile + ops, detects GitHub access, installs utilities, surfaces reminders.
- `scripts/boot.py#profile` — Load profile config entries.
- `scripts/boot.py#ops` — Load operational config entries, grouped by topic.
- `scripts/boot.py#classify_ops_key` — Route an ops key to its cognitive domain (Memory Discipline, Analysis & Delivery, etc.).
- `scripts/boot.py#group_ops_by_topic` — Organize ops entries into sections for readable output.
- `scripts/boot.py#detect_github_access` — Detect available GitHub mechanisms (CLI, API, env tokens).
- `scripts/utilities.py#install_utilities` — Materialize utility-code memories to importable Python files on disk.

**Workflow:** `boot()` calls `_exec_batch` to load profile and ops in a single HTTP request, groups ops by topic, detects environment capabilities (GitHub, env files), installs utilities from memory, and returns formatted context for the conversation window.

---

## Task Tracking

Structural forcing function for multi-step work. Tasks have named steps, type-specific checklists, and a completion gate that prevents finishing without storing results.

**Key symbols:**
- `scripts/task.py#Task` — Core class with steps, completion tracking, and persistence.
- `scripts/task.py#task` — Factory function to create a tracked task.
- `scripts/task.py#task_resume` — Load a persisted task for cross-session continuity.
- `scripts/task.py#incomplete_tasks` — List persisted incomplete tasks (surfaced at boot).

**Workflow:** `t = task("analyze X", steps=["research", "synthesize", "store"])` creates a Task. Call `t.done("research")` as steps complete. `t.complete()` gates on all required steps (including store). Tasks persist to config for cross-session pickup.

---

## Therapy & Reflection

Structured self-maintenance sessions: scope analysis, cross-episodic reflection, and session counting.

**Key symbols:**
- `scripts/boot.py#therapy_scope` — Get cutoff timestamp and unprocessed memories for a therapy session.
- `scripts/boot.py#therapy_session_count` — Count completed therapy sessions.
- `scripts/boot.py#therapy_reflect` — Cross-episodic reflection: cluster similar experiences and extract patterns.
- `scripts/boot.py#decisions_recent` — Surface recent high-confidence decisions for review.

---

## Journal

Lightweight session logging with topic tracking and intent capture.

**Key symbols:**
- `scripts/boot.py#journal` — Record a journal entry with topics, user-stated context, and agent intent.
- `scripts/boot.py#journal_recent` — Get recent entries for boot context.
- `scripts/boot.py#journal_prune` — Remove old entries, keeping the most recent N.

---

## Session Management

Save and resume conversation checkpoints. Export and import full system state.

**Key symbols:**
- `scripts/boot.py#session_save` — Save a checkpoint with summary and context.
- `scripts/boot.py#session_resume` — Resume from the most recent checkpoint.
- `scripts/boot.py#sessions` — List available checkpoints.
- `scripts/boot.py#muninn_export` — Export all state (memories + config) as portable JSON.
- `scripts/boot.py#muninn_import` — Import state from exported JSON, with optional merge mode.

---

## Handoff Workflow

Cross-environment task delegation between Claude.ai and Claude Code.

**Key symbols:**
- `scripts/boot.py#handoff_pending` — Get unfinished handoff instructions.
- `scripts/boot.py#handoff_complete` — Mark a handoff done by superseding with completion notes.

---

## Database Layer

All persistence goes through a Turso (libSQL) HTTP API. Memories use FTS5 for full-text search. The schema supports soft-delete, versioning via supersede chains, and batch operations.

**Key symbols:**
- `scripts/turso.py` — HTTP client for Turso: `_exec()`, `_exec_batch()`, `_fts5_search()`.
- `scripts/bootstrap.py#create_tables` — Schema creation (memories + config tables).
- `scripts/bootstrap.py#migrate_schema` — Add columns to existing tables for version upgrades.
- `scripts/bootstrap.py#seed_config` — Seed minimal required config entries.
- `scripts/state.py#get_session_id` — Session identity for scoping operations.
