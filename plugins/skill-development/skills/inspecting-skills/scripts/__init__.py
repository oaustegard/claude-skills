"""Scripts for skill inspection and import utilities."""

from .discover import (
    SkillLayout,
    discover_skill,
    discover_all_skills,
    skill_name_to_module,
    module_to_skill_name,
    find_skill_by_name,
)

from .index import (
    Symbol,
    ModuleIndex,
    SkillIndex,
    extract_symbols,
    index_skill,
    index_all_skills,
    generate_registry,
)

from .skill_imports import (
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
