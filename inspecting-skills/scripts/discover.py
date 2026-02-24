"""
discover.py - Scan skill directories for Python code.

Detects three common layouts:
1. scripts/ subdirectory (e.g., browsing-bluesky/scripts/*.py)
2. Root-level .py files (e.g., remembering/*.py)
3. Full packages with __init__.py
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SkillLayout:
    """Describes a skill's code structure."""
    name: str                          # e.g., "browsing-bluesky"
    path: Path                         # e.g., /home/user/claude-skills/browsing-bluesky
    layout_type: str                   # "scripts" | "root" | "package" | "none"
    python_files: list[Path] = field(default_factory=list)
    has_init: bool = False             # Has __init__.py (importable as package)
    entry_module: Optional[str] = None # Primary module name for import


def discover_skill(skill_path: Path) -> Optional[SkillLayout]:
    """
    Analyze a skill directory to determine its code layout.

    Args:
        skill_path: Path to a skill directory (must contain SKILL.md)

    Returns:
        SkillLayout describing the skill's code structure, or None if invalid
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    name = skill_path.name
    python_files = []
    layout_type = "none"
    has_init = False
    entry_module = None

    # Check for __init__.py at root (makes it a package)
    root_init = skill_path / "__init__.py"
    if root_init.exists():
        has_init = True
        entry_module = name.replace("-", "_")  # browsing-bluesky -> browsing_bluesky

    # Check for scripts/ subdirectory
    scripts_dir = skill_path / "scripts"
    if scripts_dir.is_dir():
        scripts_py_files = list(scripts_dir.glob("*.py"))
        if scripts_py_files:
            layout_type = "scripts"
            python_files.extend(scripts_py_files)
            # Check for scripts/__init__.py
            if (scripts_dir / "__init__.py").exists():
                has_init = True
                if not entry_module:
                    entry_module = name.replace("-", "_")

    # Check for root-level .py files (excluding __init__.py)
    root_py_files = [
        f for f in skill_path.glob("*.py")
        if f.name != "__init__.py"
    ]
    if root_py_files:
        if layout_type == "none":
            layout_type = "root" if not has_init else "package"
        elif layout_type == "scripts":
            # Has both scripts/ and root-level - prefer "package" if has __init__
            if has_init:
                layout_type = "package"
        python_files.extend(root_py_files)

    # Determine entry module from __init__.py exports if not set
    if has_init and not entry_module:
        entry_module = name.replace("-", "_")

    return SkillLayout(
        name=name,
        path=skill_path,
        layout_type=layout_type,
        python_files=python_files,
        has_init=has_init,
        entry_module=entry_module
    )


def discover_all_skills(
    skills_root: Path,
    exclude: Optional[set[str]] = None
) -> list[SkillLayout]:
    """
    Discover all skills with Python code in a skills repository.

    Args:
        skills_root: Root directory containing skill directories
        exclude: Set of skill names to exclude (e.g., {"templates", ".uploads"})

    Returns:
        List of SkillLayout objects for skills with Python code
    """
    exclude = exclude or {"templates", "uploads", ".uploads", "scripts", ".github", ".git"}

    skills = []

    for entry in sorted(skills_root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue
        if entry.name in exclude:
            continue

        layout = discover_skill(entry)
        if layout and layout.layout_type != "none":
            skills.append(layout)

    return skills


def skill_name_to_module(skill_name: str) -> str:
    """
    Convert a skill name (dash-delimited) to a valid Python module name.

    Examples:
        browsing-bluesky -> browsing_bluesky
        creating-mcp-servers -> creating_mcp_servers
    """
    return skill_name.replace("-", "_")


def module_to_skill_name(module_name: str) -> str:
    """
    Convert a Python module name back to the skill name.

    Examples:
        browsing_bluesky -> browsing-bluesky
        creating_mcp_servers -> creating-mcp-servers

    Note: This is lossy - underscores could have been dashes OR underscores.
    Use skill discovery to find the actual skill directory.
    """
    return module_name.replace("_", "-")


def find_skill_by_name(
    name: str,
    skills_root: Path
) -> Optional[SkillLayout]:
    """
    Find a skill by name or module name.

    Handles both forms:
        - "browsing-bluesky" (directory name)
        - "browsing_bluesky" (Python module name)

    Args:
        name: Skill name (either form)
        skills_root: Root directory containing skill directories

    Returns:
        SkillLayout if found, None otherwise
    """
    # Try exact match first
    skill_path = skills_root / name
    if skill_path.is_dir():
        return discover_skill(skill_path)

    # Try converting underscore to dash
    dash_name = name.replace("_", "-")
    skill_path = skills_root / dash_name
    if skill_path.is_dir():
        return discover_skill(skill_path)

    # Try converting dash to underscore (less common)
    underscore_name = name.replace("-", "_")
    skill_path = skills_root / underscore_name
    if skill_path.is_dir():
        return discover_skill(skill_path)

    return None
