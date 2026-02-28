# scripts/

## client.py
Minimal Claude API client. No SDK dependency.
- `call_claude(prompt, system, model, max_tokens, temperature) → str`
- `call_claude_json(prompt, system, model, max_tokens, temperature) → dict`
- `call_parallel(prompts, model, max_tokens, max_workers) → list[str]`

## orchestrate.py
Main pipeline entry point.
- `orchestrate(context, task, model, max_tokens, synthesis_max_tokens, max_workers, skills, verbose) → dict`
- `_plan(context, task, model) → dict` — Phase 1 decomposition
- `_execute(prompts, model, max_tokens, max_workers) → list[str]` — Phase 3 parallel
- `_synthesize(original_task, collected, model, max_tokens) → str` — Phase 4

## assembler.py
Deterministic context extraction and prompt assembly.
- `extract_sections(context, headers) → str`
- `extract_lines(context, ranges) → str`
- `extract_context_subset(context, sections, line_ranges) → str`
- `build_subagent_prompt(task, context_slice, skill_system, output_hint) → dict`
- `build_all_prompts(plan, context, skills) → list[dict]`
- `collect_results(plan, subagent_responses) → str`
- `build_synthesis_prompt(original_task, collected_results) → dict`

## skill_library.py
Built-in skill definitions.
- `SKILLS: dict` — 8 analytical skills
- `get_skill(name) → dict | None`
- `list_skills() → list[str]`
- `skill_catalog() → str`
