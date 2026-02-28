"""
orchestrating-skills: Skill-aware orchestration with bash-mediated context routing.
"""

from .orchestrate import orchestrate
from .skill_library import SKILLS, get_skill, list_skills, skill_catalog
from .assembler import (
    extract_sections,
    extract_lines,
    extract_context_subset,
    build_subagent_prompt,
    build_all_prompts,
    collect_results,
    build_synthesis_prompt,
)

__all__ = [
    "orchestrate",
    "SKILLS",
    "get_skill",
    "list_skills",
    "skill_catalog",
    "extract_sections",
    "extract_lines",
    "extract_context_subset",
    "build_subagent_prompt",
    "build_all_prompts",
    "collect_results",
    "build_synthesis_prompt",
]
