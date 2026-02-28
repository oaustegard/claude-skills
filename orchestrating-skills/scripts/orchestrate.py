"""
Skill-aware orchestration with context routing.

Four-phase pipeline:
  Phase 1 (LLM):  Decompose task → JSON plan with skill assignments
  Phase 2 (code): Extract context subsets, build per-task prompts
  Phase 3 (LLM):  Parallel subagent calls with targeted context slices
  Phase 4 (code + LLM): Collect results → synthesize final answer

No external dependencies beyond httpx (stdlib-adjacent).

Usage:
    from orchestrate import orchestrate

    result = orchestrate(
        context=open("report.md").read(),
        task="Compare approaches A and B, extract key metrics, recommend one",
        verbose=True,
    )
    print(result["result"])
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Local imports — support both package and direct execution
try:
    from .client import call_claude, call_claude_json, call_parallel
    from .skill_library import SKILLS, PIPELINE_SKILLS, skill_catalog
    from .assembler import build_all_prompts, collect_results, build_synthesis_prompt
except ImportError:
    from client import call_claude, call_claude_json, call_parallel
    from skill_library import SKILLS, PIPELINE_SKILLS, skill_catalog
    from assembler import build_all_prompts, collect_results, build_synthesis_prompt

_ALL_SKILLS = {**SKILLS, **PIPELINE_SKILLS}


# ---------------------------------------------------------------------------
# Phase 1: Orchestrator — task decomposition
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM = """\
You are an orchestration planner. Given a task and context, decompose the \
task into subtasks and assign each to the most appropriate skill.

## Available Skills
{catalog}

## Rules
1. Each subtask gets exactly ONE skill from the list above, or "self".
2. Use "self" when the answer is a direct lookup — a number, a name, a date, \
a definition — that requires no reasoning, analysis, or comparison. If you \
already know the answer from reading the context, include it inline.
3. For "self" tasks, include an "answer" field with your direct response.
4. Context pointers use section headers (preferred) or line ranges (fallback). \
Only include sections actually needed — don't pass everything.
5. Produce 1–6 subtasks. Fewer is better when the task is coherent.
6. Subtasks that need analysis, comparison, evaluation, or synthesis → delegate. \
Subtasks that are factual lookups from what you just read → self-answer.

## Output Schema
Return ONLY valid JSON:
{{
  "subtasks": [
    {{
      "task": "what this subtask should accomplish",
      "skill": "skill_name or self",
      "context_pointers": {{
        "sections": ["Header 1", "Header 2"],
        "line_ranges": [[1, 50]]
      }},
      "answer": "inline answer (only for skill=self)"
    }}
  ],
  "reasoning": "brief explanation of decomposition strategy"
}}"""


def _plan(
    context: str,
    task: str,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """Phase 1: LLM reads full context once, produces decomposition plan."""
    system = ORCHESTRATOR_SYSTEM.format(catalog=skill_catalog())
    prompt = f"## Task\n{task}\n\n## Context\n{context}"

    plan = call_claude_json(
        prompt=prompt,
        system=system,
        model=model,
        max_tokens=4096,
        temperature=0.2,
    )

    if "subtasks" not in plan:
        raise ValueError("Orchestrator plan missing 'subtasks' key")
    for i, st in enumerate(plan["subtasks"]):
        if "task" not in st or "skill" not in st:
            raise ValueError(f"Subtask {i} missing required keys")

    return plan


# ---------------------------------------------------------------------------
# Phase 3: Parallel subagent execution
# ---------------------------------------------------------------------------

def _execute(
    prompts: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2048,
    max_workers: int = 5,
) -> list[str]:
    """Phase 3: Run subagent prompts in parallel."""
    if not prompts:
        return []
    return call_parallel(
        prompts=prompts,
        model=model,
        max_tokens=max_tokens,
        max_workers=max_workers,
    )


# ---------------------------------------------------------------------------
# Phase 4+: Persistence via remember skill
# ---------------------------------------------------------------------------

_REMEMBER_SEARCH_PATHS = [
    "/mnt/skills/user/remembering",
    "/home/user/claude-skills/remembering",
]


def _persist(
    task: str,
    synthesized_result: str,
    subtask: dict,
    model: str = "claude-sonnet-4-6",
    verbose: bool = False,
) -> Optional[str]:
    """
    Execute a remember subtask: distill findings and write to long-term memory.

    Uses the remembering skill's scripts directly (same process, not a subagent).
    Returns the memory ID on success, None if the skill is unavailable.
    """
    # Locate and import remembering scripts
    _remember = None
    for search_path in _REMEMBER_SEARCH_PATHS:
        if Path(search_path).exists() and search_path not in sys.path:
            sys.path.insert(0, search_path)
    try:
        from scripts import remember as _remember  # type: ignore[import]
    except ImportError:
        if verbose:
            print("[orchestrate] remember skill unavailable — skipping persistence", file=sys.stderr)
        return None

    # Use LLM to distill the findings into a storable memory
    remember_skill = PIPELINE_SKILLS["remember"]
    distill_prompt = (
        f"## Original Task\n{task}\n\n"
        f"## Analysis Findings\n{synthesized_result}\n\n"
        f"## Persist Goal\n{subtask.get('task', 'Store key findings from this analysis')}"
    )
    try:
        raw = call_claude_json(
            prompt=distill_prompt,
            system=remember_skill["system_prompt"],
            model=model,
            max_tokens=512,
        )
        content = raw.get("content", "")
        mem_type = raw.get("type", "analysis")
        tags = raw.get("tags", [])
        priority = int(raw.get("priority", 0))
    except Exception:
        # Fallback: persist a brief summary directly
        content = f"{task}: {synthesized_result[:500]}"
        mem_type = "analysis"
        tags = []
        priority = 0

    if not content:
        content = f"{task}: {synthesized_result[:500]}"

    try:
        memory_id = _remember(content, mem_type, tags=tags, priority=priority)
        if verbose:
            print(f"[orchestrate] Persisted → {memory_id}", file=sys.stderr)
        return str(memory_id)
    except Exception as e:
        if verbose:
            print(f"[orchestrate] Persistence failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Phase 4: Synthesis
# ---------------------------------------------------------------------------

def _synthesize(
    original_task: str,
    collected: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> str:
    """Phase 4: Synthesize collected results into final response."""
    synth = build_synthesis_prompt(original_task, collected)
    return call_claude(
        prompt=synth["prompt"],
        system=synth["system"],
        model=model,
        max_tokens=max_tokens,
        temperature=0.3,
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def orchestrate(
    context: str,
    task: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2048,
    synthesis_max_tokens: int = 4096,
    max_workers: int = 5,
    skills: Optional[dict] = None,
    persist: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run the full four-phase orchestration pipeline.

    Args:
        context: Full context to process
        task: What to accomplish
        model: Claude model for all phases
        max_tokens: Max tokens per subagent response (default 2048)
        synthesis_max_tokens: Max tokens for final synthesis (default 4096)
        max_workers: Max concurrent subagent calls
        skills: Optional custom skill library (overrides built-in analytical skills)
        persist: If True, automatically append a remember subtask to store findings
        verbose: Print phase progress to stderr

    Returns:
        Dict with result, plan, subtask_count, self_answered, delegated, memory_ids
    """
    # Merge caller-supplied skills with built-in analytical + pipeline skills
    skill_lib = {**_ALL_SKILLS, **(skills or {})}

    def log(msg: str):
        if verbose:
            print(f"[orchestrate] {msg}", file=sys.stderr)

    # Phase 1: Decompose
    log("Phase 1: Planning...")
    plan = _plan(context, task, model=model)

    # Inject a remember subtask when persist=True (unless planner already included one)
    if persist and not any(st.get("skill") == "remember" for st in plan.get("subtasks", [])):
        plan["subtasks"].append({
            "task": "Store the key findings and conclusions from this analysis",
            "skill": "remember",
            "context_pointers": {},
        })
        log("  Injected remember subtask (persist=True)")

    subtasks = plan.get("subtasks", [])
    remember_subtasks = [st for st in subtasks if st.get("skill") == "remember"]
    self_answered = sum(1 for st in subtasks if st.get("skill") == "self")
    delegated = len(subtasks) - self_answered - len(remember_subtasks)
    log(f"  {len(subtasks)} subtasks: {self_answered} self, {delegated} delegated, "
        f"{len(remember_subtasks)} remember")

    if delegated == 0:
        log("All self-answered, collecting...")
        collected = collect_results(plan, [], skills=skill_lib)
        if len(subtasks) - len(remember_subtasks) > 1:
            log("Phase 4: Synthesizing...")
            result = _synthesize(task, collected, model=model, max_tokens=synthesis_max_tokens)
        else:
            result = next(
                (st.get("answer", collected) for st in subtasks if st.get("skill") == "self"),
                collected,
            )
        memory_ids = _run_remember_subtasks(
            remember_subtasks, task, result, model=model, verbose=verbose
        )
        return {
            "result": result,
            "plan": plan,
            "subtask_count": len(subtasks),
            "self_answered": self_answered,
            "delegated": 0,
            "memory_ids": memory_ids,
        }

    # Phase 2: Assemble (deterministic)
    log("Phase 2: Assembling prompts...")
    prompts = build_all_prompts(plan, context, skill_lib)
    log(f"  {len(prompts)} prompts built")

    # Phase 3: Execute parallel
    log(f"Phase 3: Executing {len(prompts)} subagents...")
    responses = _execute(prompts, model=model, max_tokens=max_tokens, max_workers=max_workers)
    log(f"  {len(responses)} responses received")

    # Phase 4: Synthesize
    log("Phase 4: Synthesizing...")
    collected = collect_results(plan, responses, skills=skill_lib)
    result = _synthesize(task, collected, model=model, max_tokens=synthesis_max_tokens)

    # Phase 4+: Persist (remember subtasks execute after synthesis)
    memory_ids = _run_remember_subtasks(
        remember_subtasks, task, result, model=model, verbose=verbose
    )

    return {
        "result": result,
        "plan": plan,
        "subtask_count": len(subtasks),
        "self_answered": self_answered,
        "delegated": delegated,
        "memory_ids": memory_ids,
    }


def _run_remember_subtasks(
    remember_subtasks: list[dict],
    task: str,
    synthesized_result: str,
    model: str = "claude-sonnet-4-6",
    verbose: bool = False,
) -> list[str]:
    """Execute all remember subtasks and return list of stored memory IDs."""
    if not remember_subtasks:
        return []
    memory_ids = []
    for st in remember_subtasks:
        mid = _persist(task, synthesized_result, st, model=model, verbose=verbose)
        if mid:
            memory_ids.append(mid)
    return memory_ids


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Skill-aware orchestration")
    parser.add_argument("--context-file", "-c", required=True)
    parser.add_argument("--task", "-t", required=True)
    parser.add_argument("--model", "-m", default="claude-sonnet-4-6")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--max-workers", type=int, default=5)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    context = Path(args.context_file).read_text()

    result = orchestrate(
        context=context, task=args.task, model=args.model,
        max_tokens=args.max_tokens, max_workers=args.max_workers,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["result"])


if __name__ == "__main__":
    main()
