# flowing - Changelog

All notable changes to the `flowing` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.4.0] - 2026-06-03

### Other

- flowing v1.4.0: content-addressed durable journal (cross-session resume) (#682)
- Add surface routing to orchestration skills (native CC workflows vs custom) (#675)

## [1.4.0] - 2026-06-02

### Added

- **Content-addressed durable journal (`Flow(journal_path=...)`)** — opt-in cross-process replay, adapted from the StepKey/divergence design in `antstanley/pi-flow` specs 07. Each succeeded task appends a `Completed` entry to an append-only JSONL, keyed by a chained `step_key` = SHA-256 over the task body's bytecode + its `when`/`validate`/`retry_until` fingerprints + sorted dependency keys. A subsequent `run()` — including in a fresh container after the in-memory `self.results` is gone — replays the unchanged prefix from the journal and executes only tasks whose key is absent. This delivers the cross-session checkpoint `SKILL.md` already advertised but `resume()` only provided in-memory.
- **Divergence + cascade** — editing a task body changes its `step_key`; key chaining means its dependents' keys change too, so the edited task and everything downstream re-run while the unchanged upstream prefix stays cached. Cosmetic knobs (`retry`, `retry_backoff_*`, `timeout_s`, `detached`, `name`) are excluded from the key, so tuning them does not bust the cache.
- **Crash tolerance** — journal load discards a truncated trailing line (partial write on crash) rather than failing; non-picklable return values are skipped with a log line and simply re-run on the next pass.
- `StepResult` gains `step_key` and `cached` fields (both `None`/`False` on the no-journal path, which is byte-for-byte unchanged).
- New `compute_step_key()` / `STEP_KEY_VERSION` module surface; 5 new journal tests (33 total).

### Notes

- The fingerprint hashes the task's own code, not values it closes over — a task parameterized by a captured variable will not see that variable change reflected in its key. Pass inputs through `depends_on` (the flowing analog of pi-flow's explicit `args`) for them to participate in divergence.

## [1.3.2] - 2026-05-15

### Other

- flowing v1.3.2: add human-facing README.md (#648)

## [1.3.2] - 2026-05-14

### Added

- **`README.md`** — human-facing overview for browsing the skill on GitHub, missing until now. Frames the problem (prose imperatives get generated past; a `@task` graph is structural), summarizes the three control-flow primitives, maps the file layout by audience, and points to sibling orchestration skills. Complements `SKILL.md` (agent instructions) and `references/reference.md` (agent reference).

## [1.3.1] - 2026-05-14

### Other

- flowing v1.3.1: move API reference out of SKILL.md into references/ (#647)

## [1.3.1] - 2026-05-14

### Changed

- **SKILL.md trimmed to imperative instructions.** The exhaustive API reference — full `@task` signature, `Flow` methods, resume/override, detached auto-discovery, and the `validate=`/`when=` signature gotcha — was reference material *about* the skill, not instructions *to* the agent. Moved it to `references/reference.md` (progressive disclosure); SKILL.md now keeps the trigger, mental model, quick start, the three control-flow primitives, when/when-not-to-use, and a pointer to the reference. Dropped inline version-annotation cruft (`v1.1`, `v1.2.0`, `v1.3`) that belongs in this changelog.

## [1.3.0] - 2026-05-14

### Other

- flowing v1.3.0: enforce timeout_s, validate signatures, prune dead code (#646)

## [1.3.0] - 2026-05-14

### Added

- **`timeout_s` is now enforced.** It was declared on `TaskDef` and accepted by `@task` but never read — the body ran unbounded. A task with `timeout_s` set now runs in a one-shot worker; overrunning the limit aborts the attempt as a retryable `TimeoutError` that consumes the `retry=` budget. Python can't kill the orphaned thread, so it runs until the container exits (acceptable for run-once use).
- **Graph-build-time signature validation.** `flow.run()` now checks that every task body has a parameter for each of its dependencies (or `**kwargs`). A mismatch raises a clear `ValueError` naming both tasks, instead of failing mid-run with a confusing `TypeError`.
- **`clear_registry()`** — module-level helper to empty `_TASK_REGISTRY`. Lets tests and long-lived REPLs run independent flows without stale detached tasks leaking across them via auto-discovery.
- 8 new tests (timeout enforcement + retry interaction, signature validation, registry clearing). Suite now 28 tests.

### Fixed

- **`fail_fast` parallel cancellation** now uses `pool.shutdown(wait=False, cancel_futures=True)`, which cancels queued-but-unstarted siblings. Siblings already running still can't be killed; the guarantee is "the next layer won't start," now stated explicitly in code and SKILL.md.
- **`summary()` was O(n²)** — it rebuilt the task-def set on every row. Built once now, and it also picks up auto-discovered detached tasks that the old terminal-only walk missed.

### Removed

- Dead `traceback` import and unused `functools.wraps` import.
- `StepState.PENDING`, `RUNNING`, `RETRYING` — defined but never assignable, since `_run_step` is synchronous and only ever returns a terminal state.
- Dead `_topo_sort()` function — superseded by `Flow._build_layers` and never called.
- `Flow._all_task_defs()` — folded into `summary()`'s single call to `_collect_tasks()`.

## [1.2.1] - 2026-05-08

### Other

- Add flowing/SKILL.md (#627)

## [1.2.0] - 2026-05-08

### Added

- add mapping-features skill for behavioral web app documentation (#432)
- add deep_read sub-agent for context-lean page processing

### Fixed

- auto-discover detached tasks downstream of terminals (v1.2.0) (#613)

### Other

- flowing v1.1: add when=, validate=, retry_until= control-flow primitives (#611)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
- Regenerate _MAP.md files after @lat: backlink insertion (#504)
- Lattice v2: bidirectional source-anchored knowledge graph (#503)

## [1.2.0] - 2026-05-07

### Fixed

- **Detached tasks downstream of terminals are now auto-discovered.** In v1.1.1, `Flow(main)` would silently skip a `@task(detached=True, depends_on=[main])` defined elsewhere; the task had to be passed as an additional terminal (`Flow(main, side_effect)`). The SKILL.md said "Run in a final layer after the main DAG" which implied auto-discovery. Now matches the docs: any detached task in the module registry whose `depends_on` are all reachable from declared terminals joins the run automatically. Detached tasks with unreachable deps are still ignored (they belong to a different graph).
- **Detached-on-detached chains now layer correctly.** Previously `_execute_detached` ran all detached tasks in one parallel layer, so `detachB(depends_on=[detachA], detached=True)` would be SKIPPED because `detachA` hadn't completed yet. Detached execution now uses topological layering inside the detached subset.

### Added

- Module-level `_TASK_REGISTRY` populated by the `@task` decorator. Used by `Flow._collect_tasks` to find detached candidates for auto-discovery.
- Test class `TestDetachedAutoDiscovery` (5 tests): direct downstream auto-discovery, backward-compat with explicit terminal, detached-on-detached chains, isolation of unrelated detached tasks, failure-isolation preservation. Total suite now 20 tests.

## [1.1.1] - 2026-05-07

### Documentation

- SKILL.md: added "Validator and predicate signatures" subsection clarifying that `validate=` and `when=` callables receive gathered dep values as kwargs by dep name. Reusing a validator across tasks with differently-named deps raises `TypeError` at validate time, surfacing as a confusing FAIL. Documents two patterns to handle reuse: `**kwargs` lookup and a name-binding factory.

## [1.1.0] - 2026-05-07

### Added

- **`when=` — conditional gate.** Receives gathered dep values as kwargs; falsy return marks the task SKIPPED and propagates to dependents. Use for branch selection in DAG topology rather than in-body `if` statements that no-op downstream tasks.
- **`validate=` — edge contract.** Receives gathered dep values as kwargs; raise marks the task FAILED with **no retry** (bad inputs don't fix themselves). Validator runs before the task body; on failure the body never executes and the retry budget is preserved (`attempts=0`).
- **`retry_until=` — predicate-driven loop.** Receives the task's return value; falsy return triggers a retry that consumes the existing `retry=` budget (with the same exponential backoff). On exhaustion, the last value is preserved on the FAILED result for diagnostics. Distinct from `retry=` alone, which only retries on raised exception — this retries on output shape.
- Test suite at `tests/test_flowing.py` covering backward compat (chains, retry, fail propagation, override+resume), the three new primitives, and their composition. 15 tests, all green.

### Changed

- SKILL.md reframed: control-first rather than throughput-first. Original motivation (cut serial tool calls to fit the 20/turn budget) is no longer the primary lever — the budget is now 50/turn and tool calls are faster. Control flow that doesn't bluff past gates is the durable value.

## [1.0.0] - 2026-03-20

### Added

- Add flowing skill — standalone DAG runner with resume, override, and detached tasks