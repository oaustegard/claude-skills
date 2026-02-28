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
    from .skill_library import SKILLS, skill_catalog
    from .assembler import build_all_prompts, collect_results, build_synthesis_prompt
except ImportError:
    from client import call_claude, call_claude_json, call_parallel
    from skill_library import SKILLS, skill_catalog
    from assembler import build_all_prompts, collect_results, build_synthesis_prompt


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
        skills: Optional custom skill library (overrides built-in)
        verbose: Print phase progress to stderr

    Returns:
        Dict with result, plan, subtask_count, self_answered, delegated
    """
    skill_lib = skills or SKILLS

    def log(msg: str):
        if verbose:
            print(f"[orchestrate] {msg}", file=sys.stderr)

    # Phase 1: Decompose
    log("Phase 1: Planning...")
    plan = _plan(context, task, model=model)

    subtasks = plan.get("subtasks", [])
    self_answered = sum(1 for st in subtasks if st.get("skill") == "self")
    delegated = len(subtasks) - self_answered
    log(f"  {len(subtasks)} subtasks: {self_answered} self, {delegated} delegated")

    if delegated == 0:
        log("All self-answered, collecting...")
        collected = collect_results(plan, [])
        if len(subtasks) > 1:
            log("Phase 4: Synthesizing...")
            result = _synthesize(task, collected, model=model, max_tokens=synthesis_max_tokens)
        else:
            result = subtasks[0].get("answer", collected)
        return {
            "result": result,
            "plan": plan,
            "subtask_count": len(subtasks),
            "self_answered": self_answered,
            "delegated": 0,
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
    collected = collect_results(plan, responses)
    result = _synthesize(task, collected, model=model, max_tokens=synthesis_max_tokens)

    return {
        "result": result,
        "plan": plan,
        "subtask_count": len(subtasks),
        "self_answered": self_answered,
        "delegated": delegated,
    }


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
