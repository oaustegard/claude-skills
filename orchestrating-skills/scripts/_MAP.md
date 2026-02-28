# scripts/
*Files: 5*

## Files

### __init__.py
> Imports: `.orchestrate`
- *No top-level symbols*

### assembler.py
> Imports: `re, typing`
- **extract_sections** (f) `(context: str, headers: list[str])` :19
- **extract_lines** (f) `(context: str, ranges: list[tuple[int, int]])` :62
- **extract_context_subset** (f) `(
    context: str,
    sections: Optional[list[str]] = None,
    line_ranges: Optional[list[tuple[int, int]]] = None,
)` :73
- **build_subagent_prompt** (f) `(
    task_description: str,
    context_slice: str,
    skill_system: str,
    output_hint: str,
)` :95
- **build_all_prompts** (f) `(plan: dict, context: str, skills: dict)` :116
- **collect_results** (f) `(plan: dict, subagent_responses: list[str], skills: dict | None = None)` :156
- **build_synthesis_prompt** (f) `(original_task: str, collected_results: str)` :189

### client.py
> Imports: `json, os, re, concurrent.futures, pathlib`
- **call_claude** (f) `(
    prompt: str,
    system: str = "",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    temperature: float = 0.3,
)` :42
- **call_claude_json** (f) `(
    prompt: str,
    system: str = "",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    temperature: float = 0.2,
)` :74
- **call_parallel** (f) `(
    prompts: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
)` :89

### orchestrate.py
> Imports: `argparse, json, sys, pathlib, typing`
- **orchestrate** (f) `(
    context: str,
    task: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2048,
    synthesis_max_tokens: int = 4096,
    max_workers: int = 5,
    skills: Optional[dict] = None,
    persist: bool = False,
    verbose: bool = False,
)` :231
- **main** (f) `()` :361

### skill_library.py
- **get_skill** (f) `(name: str)` :146
- **list_skills** (f) `()` :151
- **skill_catalog** (f) `()` :156

