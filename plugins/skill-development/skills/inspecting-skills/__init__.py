"""
inspecting-skills: Discover and import Python code across skills.

Solves the dash-underscore naming mismatch between skill directories
(e.g., browsing-bluesky) and Python imports (e.g., browsing_bluesky).

Quick Start:
    from inspecting_skills import setup_skill_path, skill_import

    # Enable transparent imports
    setup_skill_path("/home/user/claude-skills")
    from browsing_bluesky import search_posts

    # Or import explicitly
    bsky = skill_import("browsing-bluesky")
    posts = bsky.search_posts("python")
"""

from .scripts import (
    # Discovery
    SkillLayout,
    discover_skill,
    discover_all_skills,
    skill_name_to_module,
    module_to_skill_name,
    find_skill_by_name,
    # Indexing
    Symbol,
    ModuleIndex,
    SkillIndex,
    extract_symbols,
    index_skill,
    index_all_skills,
    generate_registry,
    # Importing
    get_skills_root,
    set_skills_root,
    setup_skill_path,
    skill_import,
    register_skill,
    list_importable_skills,
)

__all__ = [
    # Discovery
    "SkillLayout",
    "discover_skill",
    "discover_all_skills",
    "skill_name_to_module",
    "module_to_skill_name",
    "find_skill_by_name",
    # Indexing
    "Symbol",
    "ModuleIndex",
    "SkillIndex",
    "extract_symbols",
    "index_skill",
    "index_all_skills",
    "generate_registry",
    # Importing
    "get_skills_root",
    "set_skills_root",
    "setup_skill_path",
    "skill_import",
    "register_skill",
    "list_importable_skills",
]
