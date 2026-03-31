# Features: remembering

> Persistent memory system for an AI agent (Muninn). Stores typed, tagged, prioritized memories in a Turso database with BM25 full-text search, and loads identity/operational config at conversation start.

**Capability areas:**
- **[Memory Operations](#memory-operations)** — store, retrieve, evolve, and maintain memories → [details](scripts/_FEATURES.md)
- **Boot Sequence** — load identity and ops at conversation start
- **Configuration** — two-table architecture for boot-loaded settings vs searchable memories
- **Task Tracking** — structural forcing function for multi-step work
- **Session Management** — save, resume, export, import conversation checkpoints


## Memory Operations

> The core capability: storing observations, querying them back, evolving them over time, and keeping the store healthy.

This area is documented in detail in [scripts/_FEATURES.md](scripts/_FEATURES.md).
Read it when working on storage, retrieval, memory lifecycle, maintenance, or decision tracing.

At a glance:
- **Storage** — `remember()`, batch storage, background writes
- **Retrieval** — BM25 search with tag/type/time filters, proactive hints
- **Lifecycle** — forget, supersede, reprioritize, strengthen/weaken
- **Maintenance** — consolidate, curate, prune, diagnostics
- **Decision Tracing** — structured capture with alternatives and reference chains

---

## Boot Sequence

Load identity (profile) and operational instructions (ops) from the config table at conversation start. Groups ops entries by cognitive domain for organized output.

**Key symbols:**
- `scripts/boot.py#boot` — Main entry point. Loads profile + ops, detects GitHub access, installs utilities, surfaces reminders.
- `scripts/boot.py#profile` — Load profile config entries.
- `scripts/boot.py#ops` — Load operational config entries, grouped by topic.
- `scripts/boot.py#classify_ops_key` — Route an ops key to its cognitive domain.
- `scripts/utilities.py#install_utilities` — Materialize utility-code memories to importable Python files.

**Workflow:** `boot()` calls `_exec_batch` to load profile and ops in one HTTP request, groups ops by topic, detects environment capabilities (GitHub, env files), installs utilities from memory, and returns formatted context for the conversation window.

---

## Configuration

Two-table architecture: `config` stores boot-loaded identity and operational settings; `memories` stores searchable observations. Config entries have categories (profile, ops, journal), boot_load flags, and priority for ordering.

**Key symbols:**
- `scripts/config.py#config_get` — Retrieve a config value by key.
- `scripts/config.py#config_set` — Store a config value with category, optional char limit, and read-only flag.
- `scripts/config.py#config_delete` — Remove a config entry.
- `scripts/config.py#config_list` — List entries, optionally filtered by category.

**Constraints:** Categories are: profile, ops, journal. Boot_load controls whether an entry appears in the boot context window.

---

## Task Tracking

Structural forcing function for multi-step work. Tasks have named steps, type-specific checklists, and a completion gate that prevents finishing without storing results.

**Key symbols:**
- `scripts/task.py#Task` — Core class with steps, completion tracking, and persistence.
- `scripts/task.py#task` — Factory function to create a tracked task.
- `scripts/task.py#task_resume` — Load a persisted task for cross-session continuity.

**Workflow:** `t = task("analyze X", steps=["research", "synthesize", "store"])` creates a Task. Call `t.done("research")` as steps complete. `t.complete()` gates on all required steps (including store).

---

## Session Management

Save and resume conversation checkpoints. Export and import full system state.

**Key symbols:**
- `scripts/boot.py#session_save` — Save a checkpoint with summary and context.
- `scripts/boot.py#session_resume` — Resume from the most recent checkpoint.
- `scripts/boot.py#muninn_export` — Export all state (memories + config) as portable JSON.
- `scripts/boot.py#muninn_import` — Import state from exported JSON, with optional merge mode.

---

## Database Layer

All persistence goes through a Turso (libSQL) HTTP API. Memories use FTS5 for full-text search. The schema supports soft-delete, versioning via supersede chains, and batch operations.

**Key symbols:**
- `scripts/turso.py` — HTTP client for Turso: `_exec()`, `_exec_batch()`, `_fts5_search()`.
- `scripts/bootstrap.py#create_tables` — Schema creation (memories + config tables).
- `scripts/bootstrap.py#migrate_schema` — Add columns for version upgrades.
