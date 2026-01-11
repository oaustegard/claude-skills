# Remembering skill augmentation plan (Claude Code session)

Below is a concise review of the current **/remembering** skill plus augmentation ideas, expressed strictly as planning stubs (no code changes).

## Quick review (current behavior)
- The skill uses a two-table architecture (`config` for stable state + `memories` for timestamped observations) with a local SQLite cache, background writes, and FTS-backed recall when the cache is warm.
- `remember()` and `recall()` are the core APIs; writes can be synchronous or background, and there is explicit `flush()` guidance to persist background writes before exit.
- The “session_id” field is explicitly removed in v2.0.0 of the schema (commented in code), and the CLAUDE.md notes session tracking as a known limitation.

## Augmentation ideas (plan only)

### 1) Add explicit conversation/session scoping
The memory schema currently removes `session_id` and the docs call out session tracking as a limitation. This makes it hard to isolate short-lived work sessions or reconcile Claude.ai vs. Claude Code context boundaries.

:::task-stub{title="Add session scoping to memories and recall"}
1. Update schema creation/migration in `remembering/bootstrap.py` to include a `session_id` column (and indexes for query speed).
2. Extend `remember()` in `remembering/memory.py` to accept an optional `session_id` (default from a config/env source), and persist it.
3. Add optional `session_id` filters to `recall()`, `recall_since()`, and `recall_between()` in `remembering/memory.py`.
4. Mirror the new column in cache schema and population logic in `remembering/cache.py` (both `memory_index` and `memory_full` as needed).
5. Document the session model and defaults in `remembering/SKILL.md` and `remembering/CLAUDE.md`.
:::

### 2) Harden search: parameterized queries + optional Turso-side FTS
The fallback query path uses interpolated SQL (LIKE with string formatting) and is order-sensitive, which limits accuracy and introduces SQL-injection risk if `search` includes quotes. This is noted as an edge case in the docs and visible in the query builder code.

:::task-stub{title="Make recall search safe and more accurate"}
1. Replace string-interpolated LIKE conditions in `remembering/memory.py::_query`, `recall_since`, and `recall_between` with parameterized queries.
2. Add an optional Turso-side FTS path (or FTS-like query) for direct DB fallback when cache is cold, instead of LIKE string matching.
3. Update `remembering/SKILL.md` “Edge Cases” to reflect improved search semantics.
4. Add regression tests in `remembering/tests/` to cover tricky search inputs (quotes, order changes, multi-term).
:::

### 3) Make background writes safer by default
Right now the responsibility to call `flush()` is manual and emphasized in docs; missing it risks dropping buffered writes. This is a known operational hazard for single-instance agents that can end mid-session.

:::task-stub{title="Reduce data loss risk from background writes"}
1. Add an `atexit` hook (or similar teardown guard) that calls `flush()` automatically when background writes are enabled.
2. Optionally add a `remembering` context manager that guarantees `flush()` on exit for callers who want explicit lifecycle control.
3. Document the new safety behavior in `remembering/SKILL.md` and `remembering/CLAUDE.md`.
:::

### 4) Add retrieval observability + retention/aging helpers
There’s already a recall logging table in the cache, and memories have priority, but there are no public APIs to inspect retrieval quality or implement pruning/aging policies beyond journal pruning.

:::task-stub{title="Expose retrieval metrics and lifecycle helpers"}
1. Add public functions (e.g., `recall_stats()`, `top_queries()`, `memory_histogram()`) that summarize `recall_logs` in `remembering/cache.py`.
2. Add retention helpers (e.g., `prune_by_age`, `prune_by_priority`) in `remembering/memory.py` that can soft-delete low-priority, stale memories.
3. Document suggested retention workflows and monitoring in `remembering/SKILL.md`.
:::
