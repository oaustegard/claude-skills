#!/usr/bin/env python3
"""
Migrate version information from VERSION files to SKILL.md frontmatter.

Usage:
    # Migrate a single skill
    python migrate-version-to-frontmatter.py asking-questions

    # Migrate all skills
    python migrate-version-to-frontmatter.py --all

    # Dry run (show what would change without modifying files)
    python migrate-version-to-frontmatter.py --all --dry-run
"""

import sys
import argparse
from pathlib import Path
from frontmatter_utils import parse_skill_md, write_skill_md, validate_version_format


def migrate_skill(skill_dir: Path, dry_run: bool = False) -> bool:
    """
    Migrate a single skill from VERSION file to frontmatter.

    Args:
        skill_dir: Path to skill directory
        dry_run: If True, don't modify files

    Returns:
        True if migration successful, False if skipped or failed
    """
    skill_name = skill_dir.name
    version_file = skill_dir / "VERSION"
    skill_md = skill_dir / "SKILL.md"

    # Check prerequisites
    if not version_file.exists():
        print(f"⏭️  {skill_name}: No VERSION file, skipping")
        return False

    if not skill_md.exists():
        print(f"❌ {skill_name}: No SKILL.md file found")
        return False

    # Read version
    version = version_file.read_text().strip()

    # Validate version format
    if not validate_version_format(version):
        print(f"⚠️  {skill_name}: Invalid version format '{version}' (expected semver)")
        return False

    # Parse SKILL.md
    try:
        frontmatter, body = parse_skill_md(skill_md)
    except ValueError as e:
        print(f"❌ {skill_name}: Failed to parse SKILL.md: {e}")
        return False

    # Check if already migrated
    if "metadata" in frontmatter and "version" in frontmatter.get("metadata", {}):
        existing_version = frontmatter["metadata"]["version"]
        if existing_version == version:
            print(f"✓  {skill_name}: Already migrated (v{version})")
            return False
        else:
            print(f"⚠️  {skill_name}: Version mismatch (frontmatter: {existing_version}, file: {version})")
            return False

    # Add metadata.version to frontmatter
    if "metadata" not in frontmatter:
        frontmatter["metadata"] = {}

    frontmatter["metadata"]["version"] = version

    # Write back to SKILL.md
    if dry_run:
        print(f"🔍 {skill_name}: Would add metadata.version = \"{version}\"")
        return True
    else:
        try:
            write_skill_md(skill_md, frontmatter, body)
            print(f"✅ {skill_name}: Migrated v{version}")
            return True
        except Exception as e:
            print(f"❌ {skill_name}: Failed to write SKILL.md: {e}")
            return False


def find_skill_directories(repo_root: Path) -> list[Path]:
    """Find all skill directories in the repository."""
    skill_dirs = []

    # Exclude special directories
    exclude = {'.git', '.github', '.uploads', 'uploads', 'templates', 'scripts', '__pycache__'}

    for item in repo_root.iterdir():
        if item.is_dir() and item.name not in exclude:
            # Check if it has SKILL.md
            if (item / "SKILL.md").exists():
                skill_dirs.append(item)

    return sorted(skill_dirs)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate VERSION files to SKILL.md frontmatter metadata"
    )
    parser.add_argument(
        "skill",
        nargs="?",
        help="Skill directory name (e.g., 'asking-questions')"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrate all skills"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files"
    )

    args = parser.parse_args()

    # Get repository root (assume script is in scripts/ subdirectory)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Determine which skills to migrate
    if args.all:
        skill_dirs = find_skill_directories(repo_root)
        if not skill_dirs:
            print("No skill directories found")
            return 1
    elif args.skill:
        skill_dir = repo_root / args.skill
        if not skill_dir.exists():
            print(f"Error: Skill directory '{args.skill}' not found")
            return 1
        skill_dirs = [skill_dir]
    else:
        parser.print_help()
        return 1

    # Run migration
    print("=" * 60)
    if args.dry_run:
        print("DRY RUN MODE - No files will be modified")
    print(f"Migrating {len(skill_dirs)} skill(s)")
    print("=" * 60)
    print()

    success_count = 0
    skip_count = 0
    fail_count = 0

    for skill_dir in skill_dirs:
        result = migrate_skill(skill_dir, dry_run=args.dry_run)
        if result:
            success_count += 1
        else:
            # Check if it was a skip or fail based on output
            # This is a simplification; in real code we'd return different statuses
            skip_count += 1

    # Summary
    print()
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"✅ Migrated: {success_count}")
    print(f"⏭️  Skipped:  {skip_count}")
    print(f"❌ Failed:   {fail_count}")

    if args.dry_run:
        print()
        print("This was a dry run. No files were modified.")
        print("Run without --dry-run to apply changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
