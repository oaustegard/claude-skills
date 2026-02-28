"""
Skill-aware orchestration with bash-mediated context routing.

Four-phase pipeline:
  Phase 1 (LLM):  Orchestrator decomposes task → JSON plan with skill assignments
  Phase 2 (code): Assembler extracts context subsets, builds per-task prompts
  Phase 3 (LLM):  Parallel subagent calls with targeted context slices
  Phase 4 (code + LLM): Collect results → synthesizer produces final answer

Design principle: LLMs touch context once each. All shuffling, assembly,
and collection is deterministic code.

Requires: orchestrating-agents skill (for invoke_parallel, invoke_claude_json)

Usage:
    from orchestrating_skills.scripts.orchestrate import orchestrate

    result = orchestrate(
        context="<your full context here>",
        task="Compare approaches A and B, extract key metrics, and synthesize a recommendation",
        model="claude-sonnet-4-6",
    )
    print(result)

CLI:
    python orchestrate.py --context-file input.md --task "Analyze this document"
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Optional

# Add orchestrating-agents to path for imports
_SKILL_ROOTS = [
    Path(__file__).resolve().parent.parent.parent / "orchestrating-agents" / "scripts",
    Path("/mnt/skills/user/orchestrating-agents/scripts"),
]
for _root in _SKILL_ROOTS:
    if _root.exists() and str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
        break

from claude_client import invoke_claude, invoke_claude_json, invoke_parallel  # noqa: E402

# Local imports — support both package and direct execution
try:
    from .skill_library import SKILLS, skill_catalog  # noqa: E402
    from .assembler import (  # noqa: E402
        build_all_prompts,
        collect_results,
        build_synthesis_prompt,
    )
except ImportError:
    from skill_library import SKILLS, skill_catalog  # noqa: E402
    from assembler import (  # noqa: E402
        build_all_prompts,
        collect_results,
        build_synthesis_prompt,
    )


# ---------------------------------------------------------------------------
# Phase 1: Orchestrator — task decomposition
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM = """\
You are an orchestration planner. Given a task and context, you decompose the \
task into subtasks and assign each to the most appropriate skill.

## Available Skills
{catalog}

## Rules
1. Each subtask gets exactly ONE skill assignment.
2. Use "self" as the skill for trivial subtasks (lookups, simple math, \
definitions) — you answer these inline rather than spawning a subagent.
3. For "self" tasks, include an "answer" field with your direct response.
4. Context pointers use section headers (preferred) or line ranges (fallback). \
   Only include sections/lines actually needed — don't pass everything.
5. Produce 1-6 subtasks. If the task is simple enough for one skill, use one.
6. Self-answer threshold: if a subtask needs fewer than {self_answer_ceiling} \
sentences to answer correctly, prefer "self".

## Output Schema
Return ONLY valid JSON:
{{
  "subtasks": [
    {{
      "task": "description of what this subtask should accomplish",
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
    self_answer_ceiling: int = 3,
) -> dict:
    """
    Phase 1: LLM reads full context once and produces a task decomposition plan.

    Args:
        context: Full context to analyze
        task: User's task description
        model: Model for the orchestrator
        self_answer_ceiling: Sentence threshold for self-answering

    Returns:
        Plan dict with 'subtasks' list and 'reasoning'

    Raises:
        json.JSONDecodeError: If orchestrator output isn't valid JSON
        ClaudeInvocationError: If API call fails
    """
    system = ORCHESTRATOR_SYSTEM.format(
        catalog=skill_catalog(),
        self_answer_ceiling=self_answer_ceiling,
    )

    prompt = (
        f"## Task\n{task}\n\n"
        f"## Context\n{context}"
    )

    plan = invoke_claude_json(
        prompt=prompt,
        system=system,
        model=model,
        max_tokens=4096,
        temperature=0.2,
    )

    # Validate plan structure
    if "subtasks" not in plan:
        raise ValueError("Orchestrator plan missing 'subtasks' key")

    for i, st in enumerate(plan["subtasks"]):
        if "task" not in st:
            raise ValueError(f"Subtask {i} missing 'task' key")
        if "skill" not in st:
            raise ValueError(f"Subtask {i} missing 'skill' key")

    return plan


# ---------------------------------------------------------------------------
# Phase 3: Parallel subagent execution
# ---------------------------------------------------------------------------

def _execute(
    prompts: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
) -> list[str]:
    """
    Phase 3: Run subagent prompts in parallel.

    Args:
        prompts: List of prompt dicts from assembler.build_all_prompts
        model: Model for subagents
        max_tokens: Max tokens per subagent response
        max_workers: Concurrent API calls

    Returns:
        List of response strings, ordered to match prompts
    """
    if not prompts:
        return []

    return invoke_parallel(
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
    max_tokens: int = 8192,
) -> str:
    """
    Phase 4: Synthesize collected results into a final response.

    Args:
        original_task: The user's original request
        collected: Formatted results from collect_results
        model: Model for synthesis
        max_tokens: Max tokens for final response

    Returns:
        Synthesized response string
    """
    synth = build_synthesis_prompt(original_task, collected)

    return invoke_claude(
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
    max_tokens: int = 4096,
    synthesis_max_tokens: int = 8192,
    max_workers: int = 5,
    self_answer_ceiling: int = 3,
    skills: Optional[dict] = None,
    verbose: bool = False,
) -> dict:
    """
    Run the full four-phase orchestration pipeline.

    Args:
        context: Full context to process
        task: What to accomplish with the context
        model: Claude model for all phases
        max_tokens: Max tokens per subagent response
        synthesis_max_tokens: Max tokens for final synthesis
        max_workers: Max concurrent subagent calls
        self_answer_ceiling: Sentence count below which orchestrator self-answers
        skills: Optional custom skill library (defaults to built-in SKILLS)
        verbose: Print phase progress to stderr

    Returns:
        Dict with:
            - result: Final synthesized response
            - plan: Orchestrator's decomposition plan
            - subtask_count: Total subtasks
            - self_answered: Count of self-answered subtasks
            - delegated: Count of delegated subtasks
    """
    skill_lib = skills or SKILLS

    def log(msg: str):
        if verbose:
            print(f"[orchestrate] {msg}", file=sys.stderr)

    # Phase 1: Orchestrator decomposes task
    log("Phase 1: Planning task decomposition...")
    plan = _plan(context, task, model=model, self_answer_ceiling=self_answer_ceiling)

    subtasks = plan.get("subtasks", [])
    self_answered = sum(1 for st in subtasks if st.get("skill") == "self")
    delegated = len(subtasks) - self_answered

    log(f"  {len(subtasks)} subtasks: {self_answered} self-answered, {delegated} delegated")

    if delegated == 0:
        # All subtasks self-answered — skip phases 2-4, just collect
        log("All subtasks self-answered. Collecting results...")
        collected = collect_results(plan, [])

        # Still synthesize if multiple self-answered subtasks
        if len(subtasks) > 1:
            log("Phase 4: Synthesizing self-answered results...")
            result = _synthesize(
                task, collected,
                model=model, max_tokens=synthesis_max_tokens,
            )
        else:
            # Single self-answered task — just return the answer
            result = subtasks[0].get("answer", collected)

        return {
            "result": result,
            "plan": plan,
            "subtask_count": len(subtasks),
            "self_answered": self_answered,
            "delegated": 0,
        }

    # Phase 2: Assemble subagent prompts (deterministic — no LLM)
    log("Phase 2: Assembling subagent prompts...")
    prompts = build_all_prompts(plan, context, skill_lib)
    log(f"  Built {len(prompts)} prompts")

    # Phase 3: Execute subagents in parallel
    log(f"Phase 3: Executing {len(prompts)} subagents in parallel...")
    responses = _execute(
        prompts, model=model, max_tokens=max_tokens, max_workers=max_workers,
    )
    log(f"  Received {len(responses)} responses")

    # Phase 4: Collect and synthesize
    log("Phase 4: Collecting results and synthesizing...")
    collected = collect_results(plan, responses)
    result = _synthesize(
        task, collected,
        model=model, max_tokens=synthesis_max_tokens,
    )

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
    parser = argparse.ArgumentParser(
        description="Skill-aware orchestration with context routing"
    )
    parser.add_argument(
        "--context-file", "-c",
        required=True,
        help="Path to context file (markdown or text)",
    )
    parser.add_argument(
        "--task", "-t",
        required=True,
        help="Task description",
    )
    parser.add_argument(
        "--model", "-m",
        default="claude-sonnet-4-6",
        help="Claude model to use (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Max tokens per subagent (default: 4096)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Max parallel subagents (default: 5)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print phase progress to stderr",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full result as JSON (includes plan metadata)",
    )

    args = parser.parse_args()

    # Read context
    context_path = Path(args.context_file)
    if not context_path.exists():
        print(f"Error: context file not found: {context_path}", file=sys.stderr)
        sys.exit(1)

    context = context_path.read_text()

    result = orchestrate(
        context=context,
        task=args.task,
        model=args.model,
        max_tokens=args.max_tokens,
        max_workers=args.max_workers,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["result"])


if __name__ == "__main__":
    main()
