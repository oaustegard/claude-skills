"""Scripts for skill inspection and import utilities."""

from .discover import (
    SkillLayout,
    discover_all_skills,
    discover_skill,
    find_skill_by_name,
    module_to_skill_name,
    skill_name_to_module,
)
from .index import (
    ModuleIndex,
    SkillIndex,
    Symbol,
    extract_symbols,
    generate_registry,
    index_all_skills,
    index_skill,
)
from .skill_imports import (
    get_skills_root,
    list_importable_skills,
    register_skill,
    set_skills_root,
    setup_skill_path,
    skill_import,
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
