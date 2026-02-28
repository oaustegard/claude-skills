"""
Deterministic context assembly and result collection.

This module handles the "bash-mediated" phases of the orchestration pipeline:
- Phase 2: Extract context subsets, locate skills, assemble per-task prompts
- Phase 4 (partial): Collect and format subagent results for synthesis

No LLM calls happen here — only string manipulation and data routing.
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------

def extract_sections(context: str, headers: list[str]) -> str:
    """
    Extract named sections from markdown-style context.

    Uses section headers as structural pointers. Each requested header pulls
    everything from that header to the next header of equal or higher level.

    Args:
        context: Full context string (markdown with ## headers)
        headers: List of section header strings to extract (case-insensitive)

    Returns:
        Concatenated extracted sections separated by blank lines.
        If no headers match, returns empty string.
    """
    if not headers:
        return ""

    # Normalize requested headers for matching
    wanted = {h.strip().lower().lstrip("#").strip() for h in headers}

    lines = context.split("\n")
    sections: list[str] = []
    current_section: list[str] = []
    capturing = False
    capture_level = 0

    for line in lines:
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)

        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip().lower()

            # If we were capturing and hit same or higher level, stop
            if capturing and level <= capture_level:
                sections.append("\n".join(current_section))
                current_section = []
                capturing = False

            # Check if this header is one we want
            if title in wanted:
                capturing = True
                capture_level = level
                current_section.append(line)
                continue

        if capturing:
            current_section.append(line)

    # Flush last section
    if capturing and current_section:
        sections.append("\n".join(current_section))

    return "\n\n".join(sections)


def extract_lines(context: str, ranges: list[tuple[int, int]]) -> str:
    """
    Extract line ranges from context (1-indexed, inclusive).

    Args:
        context: Full context string
        ranges: List of (start, end) tuples, 1-indexed inclusive

    Returns:
        Extracted lines joined by newlines
    """
    lines = context.split("\n")
    extracted: list[str] = []

    for start, end in sorted(ranges):
        # Clamp to valid range (1-indexed → 0-indexed)
        s = max(0, start - 1)
        e = min(len(lines), end)
        extracted.extend(lines[s:e])

    return "\n".join(extracted)


def extract_context_subset(
    context: str,
    sections: Optional[list[str]] = None,
    line_ranges: Optional[list[tuple[int, int]]] = None,
) -> str:
    """
    Extract a context subset using section headers (primary) or line ranges (fallback).

    Section headers are preferred as they're structural and resilient to edits.
    Line ranges serve as fallback when content lacks headers.

    Args:
        context: Full context string
        sections: Section headers to extract
        line_ranges: Line ranges as fallback

    Returns:
        Extracted context subset. Returns full context if no pointers given.
    """
    parts = []

    if sections:
        section_text = extract_sections(context, sections)
        if section_text:
            parts.append(section_text)

    if line_ranges:
        line_text = extract_lines(context, line_ranges)
        if line_text:
            parts.append(line_text)

    if parts:
        return "\n\n".join(parts)

    # No pointers → return full context
    return context


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def build_subagent_prompt(
    task_description: str,
    context_slice: str,
    skill_system: str,
    output_hint: str,
) -> dict:
    """
    Assemble a single subagent prompt dict ready for invoke_parallel.

    Args:
        task_description: What the subagent should do
        context_slice: Pre-extracted context subset
        skill_system: System prompt from the skill library
        output_hint: Expected output structure hint

    Returns:
        Dict with 'system' and 'prompt' keys for invoke_parallel
    """
    user_prompt = (
        f"## Task\n{task_description}\n\n"
        f"## Context\n{context_slice}\n\n"
        f"## Expected Output\n"
        f"Produce output matching this structure: {output_hint}\n"
        f"Be concrete and cite the context. Do not fabricate information."
    )

    return {
        "system": skill_system,
        "prompt": user_prompt,
        "temperature": 0.3,
    }


def build_all_prompts(plan: dict, context: str, skills: dict) -> list[dict]:
    """
    Build prompt dicts for all subtasks in a plan.

    Args:
        plan: Orchestrator output with 'subtasks' list, each containing:
            - task: description string
            - skill: skill name from library
            - context_pointers: dict with optional 'sections' and 'line_ranges'
        context: Full original context
        skills: Skill library dict (name → skill definition)

    Returns:
        List of prompt dicts for invoke_parallel, preserving subtask order.
        Subtasks marked for self-answer (skill == "self") are excluded.
    """
    prompts = []

    for subtask in plan.get("subtasks", []):
        skill_name = subtask.get("skill", "")

        # Skip self-answered tasks — they don't get subagents
        if skill_name == "self":
            continue

        skill = skills.get(skill_name)
        if not skill:
            # Unknown skill — use a generic system prompt
            skill = {
                "system_prompt": (
                    "You are a helpful assistant. Complete the task using "
                    "only the provided context."
                ),
                "output_hint": "structured response",
            }

        # Extract context subset
        pointers = subtask.get("context_pointers", {})
        context_slice = extract_context_subset(
            context,
            sections=pointers.get("sections"),
            line_ranges=[
                tuple(r) for r in pointers.get("line_ranges", [])
            ] if pointers.get("line_ranges") else None,
        )

        prompt = build_subagent_prompt(
            task_description=subtask["task"],
            context_slice=context_slice,
            skill_system=skill["system_prompt"],
            output_hint=skill.get("output_hint", "structured response"),
        )

        prompts.append(prompt)

    return prompts


# ---------------------------------------------------------------------------
# Result collection
# ---------------------------------------------------------------------------

def collect_results(
    plan: dict,
    subagent_responses: list[str],
) -> str:
    """
    Merge self-answered tasks and subagent responses into a synthesis prompt.

    Args:
        plan: Original orchestrator plan
        subagent_responses: Responses from invoke_parallel (ordered)

    Returns:
        Formatted string combining all results for the synthesizer
    """
    parts = []
    response_idx = 0

    for i, subtask in enumerate(plan.get("subtasks", []), 1):
        task_desc = subtask.get("task", f"Subtask {i}")
        skill_name = subtask.get("skill", "")

        if skill_name == "self":
            # Self-answered by orchestrator
            answer = subtask.get("answer", "(no answer provided)")
            parts.append(
                f"### Subtask {i}: {task_desc}\n"
                f"**Skill**: self-answered by orchestrator\n"
                f"**Result**:\n{answer}"
            )
        else:
            # Subagent response
            if response_idx < len(subagent_responses):
                response = subagent_responses[response_idx]
                response_idx += 1
            else:
                response = "(no response — subagent may have failed)"

            parts.append(
                f"### Subtask {i}: {task_desc}\n"
                f"**Skill**: {skill_name}\n"
                f"**Result**:\n{response}"
            )

    return "\n\n---\n\n".join(parts)


def build_synthesis_prompt(
    original_task: str,
    collected_results: str,
) -> dict:
    """
    Build the final synthesis prompt from collected results.

    Args:
        original_task: The user's original request
        collected_results: Output from collect_results()

    Returns:
        Dict with 'system' and 'prompt' for invoke_claude
    """
    system = (
        "You are a synthesis specialist. You receive results from multiple "
        "subtask agents and combine them into a single coherent response "
        "that directly addresses the original task.\n\n"
        "Requirements:\n"
        "- Integrate results, don't just concatenate\n"
        "- Resolve any contradictions between subtask results\n"
        "- Maintain the user's original framing and intent\n"
        "- Produce a response that reads as if a single expert wrote it"
    )

    prompt = (
        f"## Original Task\n{original_task}\n\n"
        f"## Subtask Results\n\n{collected_results}\n\n"
        f"## Instructions\n"
        f"Synthesize the above subtask results into a single, coherent "
        f"response that fully addresses the original task. Integrate the "
        f"findings — don't just list them sequentially."
    )

    return {"system": system, "prompt": prompt}
