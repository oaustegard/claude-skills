#!/usr/bin/env python3
"""
Detect which skills had version changes by comparing frontmatter metadata.version.

Usage:
    python3 detect-version-changes.py <commit-before> <commit-after>

Returns:
    Space-separated list of skill directories on stdout
    Exit code 0 on success
"""

import sys
import subprocess
import yaml
from pathlib import Path


def get_skill_md_changes(commit_before: str, commit_after: str) -> list[str]:
    """Get list of SKILL.md files that changed between commits."""
    cmd = ["git", "diff", "--name-only", commit_before, commit_after]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    # Filter for SKILL.md files
    changed_files = []
    for line in result.stdout.strip().split('\n'):
        if line and line.endswith('/SKILL.md'):
            changed_files.append(line)

    return changed_files


def extract_version_from_commit(skill_md_path: str, commit: str) -> str | None:
    """Extract metadata.version from SKILL.md at specific commit."""
    try:
        # Get file content at specific commit
        cmd = ["git", "show", f"{commit}:{skill_md_path}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        content = result.stdout

        # Parse frontmatter
        if content.startswith("---\n"):
            parts = content.split("---\n", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                frontmatter = yaml.safe_load(frontmatter_text)

                if isinstance(frontmatter, dict):
                    if "metadata" in frontmatter and "version" in frontmatter["metadata"]:
                        return frontmatter["metadata"]["version"]
    except Exception:
        pass

    return None


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 detect-version-changes.py <commit-before> <commit-after>", file=sys.stderr)
        sys.exit(1)

    commit_before = sys.argv[1]
    commit_after = sys.argv[2]

    # Get changed SKILL.md files
    try:
        changed_files = get_skill_md_changes(commit_before, commit_after)
    except subprocess.CalledProcessError as e:
        print(f"Error getting changed files: {e}", file=sys.stderr)
        sys.exit(1)

    # Check which ones had version changes
    version_changed_skills = []

    for skill_md_path in changed_files:
        # Extract skill directory name
        skill_dir = str(Path(skill_md_path).parent)

        # Get version before and after
        version_before = extract_version_from_commit(skill_md_path, commit_before)
        version_after = extract_version_from_commit(skill_md_path, commit_after)

        # Check if version changed
        if version_before != version_after and version_after is not None:
            version_changed_skills.append(skill_dir)

    # Output space-separated list
    print(' '.join(version_changed_skills))
    sys.exit(0)


if __name__ == "__main__":
    main()
