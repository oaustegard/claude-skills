# orchestrating-agents - Changelog

All notable changes to the `orchestrating-agents` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.0] - 2026-03-05

### Added

- **Continuation Turn Protocol** (Task 1): `ConversationThread` now supports `send_continuation()`, `turn_count` property, `max_turns` limit, and configurable `continuation_prompt`
- **Stall Detection** (Task 2): New `StallDetector` class with activity timestamps, configurable timeout, heartbeat tracking, and background monitoring thread
- **Task Lifecycle State Machine** (Task 3): New `task_state.py` module with `TaskTracker`, `TaskState` enum, formal state transitions (Unclaimed → Claimed → Running → Completed/Failed/Cancelled), retry queuing, and category-based filtering
- **Exponential Backoff** (Task 4): New `invoke_with_retry()` in `orchestration.py` with configurable backoff (1s fixed for continuations, exponential for failures capped at max_ms)
- **Reconciliation Hook** (Task 5): New `invoke_parallel_with_reconciliation()` accepts optional `reconcile` callback to validate/prune tasks before dispatch
- **Concurrency Control** (Task 6): New `ConcurrencyLimiter` class with global and per-category semaphore-based limits
- **Managed Parallel** (Task 6): New `invoke_parallel_managed()` combining all Symphony patterns: retry, reconciliation, concurrency control, stall detection, and task tracking

### Changed

- All new parameters are optional with backward-compatible defaults — existing interfaces unchanged

## [0.2.0] - 2026-02-28

### Added

- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Changed

- migrate API credential management to project knowledge files

### Fixed

- resolve issues #311 and #312 in claude_client.py
- limit markdown ToC to h1/h2 headings only

### Other

- Update subagent models: default to Sonnet 4.6, add Haiku 4.5 support
