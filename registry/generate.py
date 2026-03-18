#!/usr/bin/env python3
"""Generate .claude-plugin/marketplace.json from SKILL.md frontmatter.

Usage:
    python registry/generate.py [SKILLS_ROOT]

Defaults to the parent directory of this script (repo root).
Outputs .claude-plugin/marketplace.json to the skills root.
"""

import json
import sys
from pathlib import Path

# Allow imports from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.frontmatter_utils import parse_skill_md
from registry.schema import Marketplace, PluginEntry

REPO = "oaustegard/claude-skills"
EXCLUDE_DIRS = {
    "templates", ".uploads", "scripts", ".github", ".git",
    "registry", ".claude", ".perch", ".dev-notes", "node_modules",
}


def discover_skill_dirs(root: Path) -> list[Path]:
    """Find all directories containing SKILL.md."""
    results = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue
        if entry.name in EXCLUDE_DIRS:
            continue
        if (entry / "SKILL.md").exists():
            results.append(entry)
    return results


def normalize_list(value) -> list[str]:
    """Normalize a string-or-list field to a list of strings."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    return [str(value)]


def build_entry(skill_dir: Path) -> PluginEntry | None:
    """Build a PluginEntry from a skill directory's SKILL.md."""
    fm, _ = parse_skill_md(skill_dir / "SKILL.md")
    meta = fm.get("metadata") or {}

    # Skip deprecated skills
    if meta.get("deprecated"):
        return None

    name = fm.get("name", skill_dir.name)
    description = fm.get("description", "")

    version = meta.get("version")
    if version is not None:
        version = str(version)

    # Build keywords from depends_on, credentials, domains
    keywords: list[str] = []
    keywords.extend(normalize_list(meta.get("depends_on")))
    keywords.extend(normalize_list(meta.get("requires")))

    return PluginEntry(
        name=name,
        description=description,
        source="./",
        strict=False,
        skills=[f"./{skill_dir.name}"],
        version=version,
        repository=f"https://github.com/{REPO}",
        license="MIT",
        keywords=keywords if keywords else [],
    )


def generate(root: Path) -> Marketplace:
    """Scan all skills and build a Marketplace manifest."""
    skill_dirs = discover_skill_dirs(root)
    marketplace = Marketplace()

    for sd in skill_dirs:
        try:
            entry = build_entry(sd)
            if entry is not None:
                marketplace.plugins.append(entry)
        except Exception as e:
            print(f"WARN: skipping {sd.name}: {e}", file=sys.stderr)

    return marketplace


def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent

    marketplace = generate(root)

    # Ensure .claude-plugin directory exists
    out_dir = root / ".claude-plugin"
    out_dir.mkdir(exist_ok=True)

    # Write marketplace.json
    out_path = out_dir / "marketplace.json"
    out_path.write_text(
        json.dumps(marketplace.to_dict(), indent=2, ensure_ascii=False) + "\n"
    )
    print(f"Wrote {out_path} ({len(marketplace.plugins)} plugins)")


if __name__ == "__main__":
    main()
