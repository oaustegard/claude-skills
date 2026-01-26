"""
skill_imports.py - Universal import mechanism for cross-skill code reuse.

Handles the dash-to-underscore naming mismatch between skill directories
(dash-delimited) and Python imports (underscore-required).

Usage:
    from inspecting_skills import skill_import, setup_skill_path

    # Simple import
    bsky = skill_import("browsing-bluesky")
    bsky.search_posts("python")

    # Import specific functions
    search_posts, get_profile = skill_import("browsing-bluesky", ["search_posts", "get_profile"])

    # Or setup path once and use normal imports
    setup_skill_path("/home/user/claude-skills")
    from browsing_bluesky import search_posts  # Works!
"""

import sys
import os
import importlib
import importlib.abc
import importlib.util
from pathlib import Path
from typing import Any, Optional, Union

from .discover import find_skill_by_name, skill_name_to_module, discover_skill


# Default skills root - can be overridden
_skills_root: Optional[Path] = None
_registered_skills: dict[str, Path] = {}


def get_skills_root() -> Optional[Path]:
    """Get the currently configured skills root directory."""
    global _skills_root
    return _skills_root


def set_skills_root(path: Union[str, Path]) -> None:
    """
    Set the skills root directory.

    Args:
        path: Path to the directory containing skill directories
    """
    global _skills_root
    _skills_root = Path(path).resolve()


def setup_skill_path(skills_root: Union[str, Path, None] = None) -> Path:
    """
    Add skills root to sys.path and enable skill imports.

    This sets up the Python path so that skills can be imported directly:
        setup_skill_path("/home/user/claude-skills")
        from browsing_bluesky import search_posts

    Args:
        skills_root: Path to skills directory. If None, attempts auto-detection.

    Returns:
        The skills root path that was configured

    Raises:
        ValueError: If skills_root cannot be determined
    """
    global _skills_root

    if skills_root:
        _skills_root = Path(skills_root).resolve()
    elif _skills_root is None:
        # Try to auto-detect from common locations
        candidates = [
            Path("/home/user/claude-skills"),
            Path("/home/claude/claude-skills"),
            Path.home() / "claude-skills",
            Path.cwd(),
        ]
        for candidate in candidates:
            if candidate.is_dir() and (candidate / ".git").exists():
                # Verify it looks like a skills repo
                skill_dirs = [d for d in candidate.iterdir()
                              if d.is_dir() and (d / "SKILL.md").exists()]
                if skill_dirs:
                    _skills_root = candidate
                    break

        if _skills_root is None:
            raise ValueError(
                "Could not auto-detect skills root. "
                "Please provide skills_root parameter."
            )

    # Add to sys.path if not already there
    path_str = str(_skills_root)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    # Register the meta path finder for transparent imports
    _ensure_finder_installed()

    return _skills_root


def skill_import(
    skill_name: str,
    symbols: Optional[list[str]] = None
) -> Any:
    """
    Import a skill module or specific symbols from it.

    Handles dash-to-underscore conversion automatically.

    Args:
        skill_name: Skill name (e.g., "browsing-bluesky" or "browsing_bluesky")
        symbols: Optional list of symbol names to import. If None, returns module.

    Returns:
        If symbols is None: The imported module
        If symbols is a list: Tuple of the requested symbols

    Examples:
        # Import the whole module
        bsky = skill_import("browsing-bluesky")
        bsky.search_posts("python")

        # Import specific functions
        search_posts, get_profile = skill_import("browsing-bluesky",
                                                  ["search_posts", "get_profile"])

        # Single symbol
        (search_posts,) = skill_import("browsing-bluesky", ["search_posts"])
    """
    # Ensure skills root is configured
    if _skills_root is None:
        setup_skill_path()

    # Find the skill
    layout = find_skill_by_name(skill_name, _skills_root)
    if layout is None:
        raise ImportError(f"Skill not found: {skill_name}")

    # Determine the module name
    module_name = skill_name_to_module(layout.name)

    # Ensure the skill path is importable
    skill_path_str = str(layout.path.parent)
    if skill_path_str not in sys.path:
        sys.path.insert(0, skill_path_str)

    # Import the module
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        # Try importing directly from the skill directory
        init_path = layout.path / "__init__.py"
        if init_path.exists():
            spec = importlib.util.spec_from_file_location(module_name, init_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            else:
                raise ImportError(f"Cannot load skill {skill_name}: {e}")
        else:
            raise ImportError(f"Skill {skill_name} has no __init__.py: {e}")

    # Return module or specific symbols
    if symbols is None:
        return module

    result = []
    for sym in symbols:
        if hasattr(module, sym):
            result.append(getattr(module, sym))
        else:
            raise ImportError(f"Symbol '{sym}' not found in skill '{skill_name}'")

    return tuple(result)


def register_skill(skill_name: str, skill_path: Union[str, Path]) -> None:
    """
    Register a skill at a custom path for importing.

    Useful when skills are not in the standard skills root.

    Args:
        skill_name: Name to register the skill under
        skill_path: Path to the skill directory
    """
    global _registered_skills
    _registered_skills[skill_name] = Path(skill_path).resolve()
    _registered_skills[skill_name_to_module(skill_name)] = Path(skill_path).resolve()


class SkillImportFinder(importlib.abc.MetaPathFinder):
    """
    Meta path finder that enables importing skills with underscore names.

    Installed by setup_skill_path() to enable:
        from browsing_bluesky import search_posts
    """

    def find_spec(self, fullname: str, path, target=None):
        if _skills_root is None:
            return None

        # Only handle top-level imports that might be skills
        parts = fullname.split(".")
        top_level = parts[0]

        # Check registered skills first
        if top_level in _registered_skills:
            skill_path = _registered_skills[top_level]
            return self._create_spec(fullname, skill_path, parts)

        # Try to find as a skill (convert underscore to dash)
        dash_name = top_level.replace("_", "-")
        skill_path = _skills_root / dash_name

        if skill_path.is_dir() and (skill_path / "SKILL.md").exists():
            return self._create_spec(fullname, skill_path, parts)

        return None

    def _create_spec(self, fullname: str, skill_path: Path, parts: list[str]):
        """Create a module spec for the skill."""
        if len(parts) == 1:
            # Top-level skill import
            init_path = skill_path / "__init__.py"
            if init_path.exists():
                return importlib.util.spec_from_file_location(
                    fullname,
                    init_path,
                    submodule_search_locations=[str(skill_path)]
                )
        else:
            # Submodule import (e.g., browsing_bluesky.scripts.bsky)
            subpath = skill_path
            for part in parts[1:]:
                subpath = subpath / part

            # Try as package
            init_path = subpath / "__init__.py"
            if init_path.exists():
                return importlib.util.spec_from_file_location(
                    fullname,
                    init_path,
                    submodule_search_locations=[str(subpath)]
                )

            # Try as module
            module_path = subpath.with_suffix(".py")
            if module_path.exists():
                return importlib.util.spec_from_file_location(
                    fullname,
                    module_path
                )

        return None


_finder_installed = False


def _ensure_finder_installed() -> None:
    """Install the SkillImportFinder if not already installed."""
    global _finder_installed
    if not _finder_installed:
        sys.meta_path.insert(0, SkillImportFinder())
        _finder_installed = True


def list_importable_skills() -> list[dict]:
    """
    List all skills that can be imported.

    Returns:
        List of dicts with skill info: name, module_name, has_init, layout_type
    """
    if _skills_root is None:
        try:
            setup_skill_path()
        except ValueError:
            return []

    from .discover import discover_all_skills

    layouts = discover_all_skills(_skills_root)
    return [
        {
            "name": layout.name,
            "module_name": layout.entry_module or skill_name_to_module(layout.name),
            "has_init": layout.has_init,
            "layout_type": layout.layout_type,
            "path": str(layout.path)
        }
        for layout in layouts
        if layout.has_init  # Only show skills that can actually be imported
    ]
