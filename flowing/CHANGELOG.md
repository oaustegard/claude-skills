# flowing - Changelog

All notable changes to the `flowing` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
