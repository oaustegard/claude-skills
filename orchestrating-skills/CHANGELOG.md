# Changelog

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
