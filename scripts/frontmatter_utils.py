#!/usr/bin/env python3
"""Utilities for working with YAML frontmatter in SKILL.md files."""

import re
import yaml
from pathlib import Path
from typing import Dict, Tuple, Any


def parse_skill_md(skill_md_path: Path) -> Tuple[Dict[str, Any], str]:
    """
    Parse a SKILL.md file into frontmatter dict and body text.

    Args:
        skill_md_path: Path to SKILL.md file

    Returns:
        Tuple of (frontmatter_dict, body_text)

    Raises:
        ValueError: If file doesn't have valid frontmatter
    """
    if not skill_md_path.exists():
        raise ValueError(f"File not found: {skill_md_path}")

    content = skill_md_path.read_text()

    # Check for frontmatter (must start with ---)
    if not content.startswith("---\n"):
        raise ValueError(f"No frontmatter found in {skill_md_path}")

    # Split on --- delimiters
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid frontmatter structure in {skill_md_path}")

    # parts[0] is empty, parts[1] is frontmatter, parts[2] is body
    frontmatter_text = parts[1]
    body = parts[2]

    # Parse YAML
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            raise ValueError("Frontmatter must be a YAML mapping")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in frontmatter: {e}")

    return frontmatter, body


def write_skill_md(skill_md_path: Path, frontmatter: Dict[str, Any], body: str) -> None:
    """
    Write frontmatter and body back to SKILL.md file.

    Args:
        skill_md_path: Path to SKILL.md file
        frontmatter: Dictionary of frontmatter fields
        body: Body text (everything after frontmatter)
    """
    # Convert frontmatter to YAML
    # Use default_flow_style=False for readable multi-line format
    frontmatter_yaml = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False  # Preserve order
    )

    # Construct file content
    content = f"---\n{frontmatter_yaml}---{body}"

    # Write to file
    skill_md_path.write_text(content)


def extract_version(skill_dir: Path) -> str:
    """
    Extract version from frontmatter or VERSION file.

    Args:
        skill_dir: Path to skill directory

    Returns:
        Version string

    Raises:
        ValueError: If no version found
    """
    skill_md = skill_dir / "SKILL.md"

    # Try frontmatter first
    if skill_md.exists():
        try:
            frontmatter, _ = parse_skill_md(skill_md)
            if "metadata" in frontmatter and "version" in frontmatter["metadata"]:
                return frontmatter["metadata"]["version"]
        except Exception:
            pass

    # Fall back to VERSION file
    version_file = skill_dir / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()

    raise ValueError(f"No version found in {skill_dir}")


def validate_version_format(version: str) -> bool:
    """
    Validate that version follows semver format.

    Args:
        version: Version string to validate

    Returns:
        True if valid, False otherwise
    """
    # Basic semver: MAJOR.MINOR.PATCH
    pattern = r'^\d+\.\d+\.\d+$'
    return bool(re.match(pattern, version))
