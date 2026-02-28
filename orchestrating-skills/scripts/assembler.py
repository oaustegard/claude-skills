"""
Deterministic context assembly and result collection.

Handles the non-LLM phases:
  Phase 2: Extract context subsets, build per-task prompts
  Phase 4 (partial): Collect and format results for synthesis
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------

def extract_sections(context: str, headers: list[str]) -> str:
    """
    Extract named sections from markdown context.

    Each header pulls content from that header to next equal-or-higher-level header.
    Case-insensitive matching, ignores leading # characters in requested headers.
    """
    if not headers:
        return ""

    wanted = {h.strip().lower().lstrip("#").strip() for h in headers}
    lines = context.split("\n")
    sections: list[str] = []
    current: list[str] = []
    capturing = False
    level = 0

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            hlevel = len(m.group(1))
            title = m.group(2).strip().lower()

            if capturing and hlevel <= level:
                sections.append("\n".join(current))
                current = []
                capturing = False

            if title in wanted:
                capturing = True
                level = hlevel
                current.append(line)
                continue

        if capturing:
            current.append(line)

    if capturing and current:
        sections.append("\n".join(current))

    return "\n\n".join(sections)


def extract_lines(context: str, ranges: list[tuple[int, int]]) -> str:
    """Extract line ranges (1-indexed, inclusive)."""
    lines = context.split("\n")
    extracted: list[str] = []
    for start, end in sorted(ranges):
        s = max(0, start - 1)
        e = min(len(lines), end)
        extracted.extend(lines[s:e])
    return "\n".join(extracted)


def extract_context_subset(
    context: str,
    sections: Optional[list[str]] = None,
    line_ranges: Optional[list[tuple[int, int]]] = None,
) -> str:
    """Extract context subset. Sections first, line ranges as fallback, full context if neither."""
    parts = []
    if sections:
        text = extract_sections(context, sections)
        if text:
            parts.append(text)
    if line_ranges:
        text = extract_lines(context, line_ranges)
        if text:
            parts.append(text)
    return "\n\n".join(parts) if parts else context


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def build_subagent_prompt(
    task_description: str,
    context_slice: str,
    skill_system: str,
    output_hint: str,
) -> dict:
    """Build a single subagent prompt dict for call_parallel."""
    user_prompt = (
        f"## Task\n{task_description}\n\n"
        f"## Context\n{context_slice}\n\n"
        f"## Output\n"
        f"Structure: {output_hint}\n"
        f"Be concrete, cite the context, do not fabricate. Be concise."
    )
    return {
        "system": skill_system,
        "prompt": user_prompt,
        "temperature": 0.3,
    }


def build_all_prompts(plan: dict, context: str, skills: dict) -> list[dict]:
    """Build prompt dicts for all delegated subtasks. Skips self-answered."""
    prompts = []

    for subtask in plan.get("subtasks", []):
        skill_name = subtask.get("skill", "")
        if skill_name == "self":
            continue

        skill = skills.get(skill_name, {
            "system_prompt": "You are a helpful assistant. Use only the provided context.",
            "output_hint": "structured response",
        })

        pointers = subtask.get("context_pointers", {})
        context_slice = extract_context_subset(
            context,
            sections=pointers.get("sections"),
            line_ranges=[tuple(r) for r in pointers.get("line_ranges", [])]
            if pointers.get("line_ranges") else None,
        )

        prompts.append(build_subagent_prompt(
            task_description=subtask["task"],
            context_slice=context_slice,
            skill_system=skill["system_prompt"],
            output_hint=skill.get("output_hint", "structured response"),
        ))

    return prompts


# ---------------------------------------------------------------------------
# Result collection
# ---------------------------------------------------------------------------

def collect_results(plan: dict, subagent_responses: list[str]) -> str:
    """Merge self-answered and subagent responses for the synthesizer."""
    parts = []
    resp_idx = 0

    for i, subtask in enumerate(plan.get("subtasks", []), 1):
        task_desc = subtask.get("task", f"Subtask {i}")
        skill = subtask.get("skill", "")

        if skill == "self":
            answer = subtask.get("answer", "(no answer)")
            parts.append(f"### Subtask {i}: {task_desc}\n[self-answered]\n{answer}")
        else:
            if resp_idx < len(subagent_responses):
                response = subagent_responses[resp_idx]
                resp_idx += 1
            else:
                response = "(no response)"
            parts.append(f"### Subtask {i}: {task_desc}\n[{skill}]\n{response}")

    return "\n\n---\n\n".join(parts)


def build_synthesis_prompt(original_task: str, collected_results: str) -> dict:
    """Build the final synthesis prompt."""
    system = (
        "You synthesize subtask results into a single coherent response.\n\n"
        "Rules:\n"
        "- Integrate findings, don't concatenate or repeat them\n"
        "- Resolve contradictions between subtask results\n"
        "- Match the user's original framing and intent\n"
        "- Write as if a single expert produced this — no 'Subtask 1 found...'\n"
        "- Be thorough but not verbose — every sentence should earn its place"
    )

    prompt = (
        f"## Original Task\n{original_task}\n\n"
        f"## Subtask Results\n\n{collected_results}\n\n"
        f"## Instructions\n"
        f"Synthesize the above into a single response that fully addresses the task. "
        f"Integrate — don't list subtask outputs sequentially. "
        f"Prioritize insight density over length."
    )

    return {"system": system, "prompt": prompt}
