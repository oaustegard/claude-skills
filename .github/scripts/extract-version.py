#!/usr/bin/env python3
"""
Extract version from SKILL.md frontmatter or VERSION file.

Usage:
    python3 extract-version.py <skill-directory>

Returns:
    Version string on stdout
    Exit code 0 on success, 1 on failure
"""

import sys
import yaml
from pathlib import Path


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
            content = skill_md.read_text()
            if content.startswith("---\n"):
                # Split on --- delimiters
                parts = content.split("---\n", 2)
                if len(parts) >= 3:
                    frontmatter_text = parts[1]
                    frontmatter = yaml.safe_load(frontmatter_text)

                    # Check metadata.version
                    if isinstance(frontmatter, dict):
                        if "metadata" in frontmatter and "version" in frontmatter["metadata"]:
                            return frontmatter["metadata"]["version"]
        except Exception:
            pass  # Fall through to VERSION file

    # Fall back to VERSION file (backward compatibility)
    version_file = skill_dir / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()

    raise ValueError(f"No version found in {skill_dir}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 extract-version.py <skill-directory>", file=sys.stderr)
        sys.exit(1)

    skill_dir = Path(sys.argv[1])

    if not skill_dir.exists():
        print(f"Error: Directory '{skill_dir}' does not exist", file=sys.stderr)
        sys.exit(1)

    try:
        version = extract_version(skill_dir)
        print(version)
        sys.exit(0)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
