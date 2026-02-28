# scripts/
*Files: 4*

## Files

### __init__.py
> Imports: `.orchestrate, .skill_library, .assembler`
- *No top-level symbols*

### assembler.py
> Imports: `re, typing`
- **extract_sections** (f) `(context: str, headers: list[str])` :21
- **extract_lines** (f) `(context: str, ranges: list[tuple[int, int]])` :78
- **extract_context_subset** (f) `(
    context: str,
    sections: Optional[list[str]] = None,
    line_ranges: Optional[list[tuple[int, int]]] = None,
)` :101
- **build_subagent_prompt** (f) `(
    task_description: str,
    context_slice: str,
    skill_system: str,
    output_hint: str,
)` :143
- **build_all_prompts** (f) `(plan: dict, context: str, skills: dict)` :176
- **collect_results** (f) `(
    plan: dict,
    subagent_responses: list[str],
)` :238
- **build_synthesis_prompt** (f) `(
    original_task: str,
    collected_results: str,
)` :284

### orchestrate.py
> Imports: `argparse, json, sys, os, pathlib`...
- **orchestrate** (f) `(
    context: str,
    task: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    synthesis_max_tokens: int = 8192,
    max_workers: int = 5,
    self_answer_ceiling: int = 3,
    skills: Optional[dict] = None,
    verbose: bool = False,
)` :230
- **main** (f) `()` :336

### skill_library.py
- **get_skill** (f) `(name: str)` :162
- **list_skills** (f) `()` :167
- **skill_catalog** (f) `()` :172

