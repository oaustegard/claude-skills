# orchestrating-agents - Changelog

All notable changes to the `orchestrating-agents` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.6.0] - 2026-08-12

### Fixed

- **Surface routing no longer claims the native runtime lacks inter-agent
  messaging.** The "reach back into this skill for what the runtime lacks" line
  listed `AgentPool` messaging alongside stall detection and
  `ConversationThread`. Claude Code and Cowork ship `SendMessage` and
  `ListAgents`; `AgentPool` reimplements them worse. The skill previously
  mentioned neither tool anywhere, so a reader following it would hand-roll a
  fan-out for messaging the runtime already provides.

### Added

- Native inter-agent messaging subsection under the native-subagents branch,
  covering four behaviors measured 2026-08-12 that the official docs do not
  state: the incoming envelope's `from` attribute is the agent *type* and fails
  as a reply address; subagents have no `ListAgents` at all, making the topology
  a star through the main conversation rather than a mesh; delivery queues and
  never interrupts a running tool; and a send resumes a completed agent with
  full context that the agent cannot detect, at transcript-replay cost.
- Note that `anthropics/claude-code#48160` and `ruvnet/ruflo#2028` report
  subagents cannot originate `SendMessage`, contradicted by a CCotw measurement
  on 2026-08-12 — flagged as environment-dependent and to be verified locally
  rather than designed around.

## [0.5.0] - 2026-07-30

### Other

- orchestrating-agents v0.5.0 — three-surface routing, Gemini via CF, credential-handling fix (#749)
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)

## [0.5.0] - 2026-07-30

### Changed

- Surface routing rewritten as a three-surface matrix (claude.ai / Cowork /
  Claude Code) against three engines (native subagents / Gemini via CF AI
  Gateway / this skill's httpx fan-out). Previously the block knew only two
  surfaces and had no Gemini row. Primary discriminator is now whether an
  `Agent`/`Task`/`Workflow` tool is callable, rather than filesystem inspection.
- Cowork documented as its own surface, including plugin-declared subagents
  (`agents/*.md`, frontmatter fields, `plugin:agent` naming) and the security
  restriction that `hooks`, `mcpServers`, and `permissionMode` are refused in
  plugin-shipped agents — a declared agent inherits the session's MCP
  connections and cannot bring its own.
- Setup no longer instructs storing `ANTHROPIC_API_KEY.txt` in project
  knowledge. Credentials must arrive by a path the shell reads directly.

### Added

- Gemini-via-Cloudflare as an explicit option on **all** surfaces, not just
  claude.ai — for mechanical-but-large work and for model-family diversity in
  judge panels. Mechanics stay in `invoking-gemini`; the three failure modes
  that bite are named here (stale `flash` alias, `thinking_level='minimal'` for
  mechanical work, BYOK through the gateway).
- "Review is not delegable" stated as a cross-surface rule, with the note that
  cross-model review tools keep their own model config.
- See Also split into routing companions (`agent-routing`, `invoking-gemini`,
  `subagent-delegation-protocol`) versus this skill's own internals.

### Fixed

- `project_read` warned against for credentials on every surface: small docs are
  returned inline, and the documented "large text is written to a local file"
  branch does not fire even at 64 KB (measured 2026-07-30). Writing is safe —
  `project_write` with `local_path` keeps contents out of context — reading is
  not.
- Token Efficiency claim corrected from "~800 tokens" to ~2k.

## [0.4.0] - 2026-04-08

### Added

- add AgentPool, EXECUTE_MODE, inter-agent messaging (v0.4.0) (#537)
- add mapping-features skill for behavioral web app documentation (#432)

### Fixed

- remove shim and local _parse_json workarounds from tiling-tree (#314)
- streaming passes system=None to API when no system prompt given

### Other

- Regenerate _MAP.md files after @lat: backlink insertion (#504)
- Lattice v2: bidirectional source-anchored knowledge graph (#503)

## [0.3.0] - 2026-03-05

### Added

- implement Symphony orchestration patterns (#349)
- Add orchestrating-skills skill (#319)

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