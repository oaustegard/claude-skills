# flowing - Changelog

All notable changes to the `flowing` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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