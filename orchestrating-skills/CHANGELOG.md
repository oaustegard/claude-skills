# Changelog

## 0.4.0 (2026-10-07)

### Changed
- Default model `claude-sonnet-4-6` -> `claude-sonnet-5-5` in `client.py`, `orchestrate.py` and docs

### Fixed
- `call_claude` no longer sends `temperature` to models that reject it (Sonnet 5.5,
  Haiku 5.5, Opus 5.x return HTTP 400); `_accepts_sampling(model)` is true only for
  legacy families. The `temperature` parameters stay in the signatures and are ignored on current models.

## 0.3.0 (2026-02-28)

### Added
- `remember` as a first-class pipeline skill (closes #328)
  - Executes post-synthesis in Phase 4, not as a parallel subagent
  - Uses LLM distillation to extract the key insight before writing to memory
  - Falls back gracefully if `remembering` skill is unavailable
- `persist=True` parameter on `orchestrate()` — auto-injects a `remember` subtask
  without requiring it in the planner's JSON
- `memory_ids` field in the return dict — list of stored memory IDs
- `PIPELINE_SKILLS` dict in `skill_library.py` for skills that run outside Phase 3

### Changed
- `collect_results()` now accepts `skills` kwarg; pipeline-only skills are excluded
  from synthesis input (storage artifacts, not analytical content)
- `build_all_prompts()` skips pipeline-only skills (they have no subagent prompt)
- `skill_catalog()` includes pipeline skills so the planner can emit them
- `orchestrate()` `skills` kwarg now **merges** with built-in skills instead of
  replacing them entirely

## 0.2.0 (2026-02-27)

### Breaking Changes
- Removed dependency on `orchestrating-agents` skill and Anthropic SDK
- Removed `self_answer_ceiling` parameter from `orchestrate()` and skill library
- Default `max_tokens` reduced from 4096 to 2048 (subagents) and 8192 to 4096 (synthesis)

### Added
- `client.py`: Minimal HTTP client using httpx (~110 lines vs 800+ in claude_client.py)
- Self-answering is now a pure LLM judgment call based on task complexity, not sentence counts

### Improved
- Total pipeline time ~47% faster (152s → 80s on test document)
  - Phase 1: 12s → 8s (cleaner planner prompt)
  - Phase 3: 51s → 30s (tighter max_tokens, fewer subtasks)
  - Phase 4: 88s → 43s (conciseness instructions, less input to synthesize)
- Planner produces fewer, better subtasks (4 → 3 on same test, dropping redundant synthesis subtask)
- Skill system prompts include conciseness instructions
- Synthesis prompt demands integration over expansion

## 0.1.0 (2026-02-27)

- Initial implementation: four-phase pipeline
- 8 built-in skills
- Section header context pointers
- Parallel execution via orchestrating-agents

## [0.4.0] - 2026-10-07

### Added

- add mapping-features skill for behavioral web app documentation (#432)
- structural task discipline for Muninn — checklists, recall gate, cross-session persistence

### Other

- Migrate hardcoded model defaults to the 5.5 generation
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)
- Add surface routing to orchestration skills (native CC workflows vs custom) (#675)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)

## [0.3.0] - 2026-02-28

### Added

- add remember as first-class pipeline skill (closes #328)

### Fixed

- add analysis memory type instead of overloading world (#328)

## [0.2.0] - 2026-02-28

### Other

- orchestrating-skills v0.2.0: drop SDK, fix self-answering, 47% faster