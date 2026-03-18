#!/usr/bin/env python3
"""Generate registry.json and llms.txt from SKILL.md frontmatter.

Usage:
    python registry/generate.py [SKILLS_ROOT]

Defaults to the parent directory of this script (repo root).
Outputs registry.json and llms.txt to the skills root.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Allow imports from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.frontmatter_utils import parse_skill_md
from registry.schema import Registry, SkillEntry
from registry.llms_txt import render_llms_txt

REPO = "oaustegard/claude-skills"
EXCLUDE_DIRS = {
    "templates", ".uploads", "scripts", ".github", ".git",
    "registry", ".claude", ".perch", ".dev-notes", "node_modules",
}
EXCLUDE_FILES = {"_MAP.md", "README.md", "CHANGELOG.md"}


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


def get_last_updated(skill_dir: Path) -> Optional[str]:
    """Get ISO 8601 timestamp of last git commit touching this directory."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(skill_dir)],
            capture_output=True, text=True, cwd=skill_dir.parent,
            timeout=10,
        )
        ts = result.stdout.strip()
        return ts if ts else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def list_skill_files(skill_dir: Path) -> list[str]:
    """List files in a skill directory, excluding generated artifacts."""
    files = []
    for f in sorted(skill_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.name in EXCLUDE_FILES:
            continue
        if "__pycache__" in f.parts:
            continue
        files.append(str(f.relative_to(skill_dir)))
    return files


def build_download_url(name: str, version: Optional[str]) -> Optional[str]:
    """Construct GitHub release download URL."""
    if not version:
        return None
    return f"https://github.com/{REPO}/releases/download/{name}-v{version}/{name}.zip"


def normalize_list(value) -> list[str]:
    """Normalize a string-or-list field to a list of strings."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    return [str(value)]


def build_entry(skill_dir: Path) -> SkillEntry:
    """Build a SkillEntry from a skill directory's SKILL.md."""
    fm, _ = parse_skill_md(skill_dir / "SKILL.md")
    meta = fm.get("metadata") or {}

    # Merge depends_on + requires into one list
    deps = normalize_list(meta.get("depends_on"))
    deps.extend(normalize_list(meta.get("requires")))

    version = meta.get("version")
    if version is not None:
        version = str(version)

    name = fm.get("name", skill_dir.name)

    return SkillEntry(
        name=name,
        description=fm.get("description", ""),
        version=version,
        deprecated=bool(meta.get("deprecated", False)),
        superseded_by=meta.get("superseded_by"),
        depends_on=deps,
        credentials=normalize_list(fm.get("credentials")),
        domains=normalize_list(fm.get("domains")),
        directory=skill_dir.name,
        last_updated=get_last_updated(skill_dir),
        download_url=build_download_url(name, version),
        files=list_skill_files(skill_dir),
    )


def generate(root: Path) -> Registry:
    """Scan all skills and build a Registry."""
    skill_dirs = discover_skill_dirs(root)

    registry = Registry(
        generated_at=datetime.now(timezone.utc).isoformat(),
        repository=REPO,
    )

    for sd in skill_dirs:
        try:
            entry = build_entry(sd)
            # Key on directory name to avoid duplicates from shared frontmatter names
            key = sd.name
            if key in registry.skills:
                print(f"WARN: duplicate directory key '{key}', overwriting", file=sys.stderr)
            registry.skills[key] = entry
        except Exception as e:
            print(f"WARN: skipping {sd.name}: {e}", file=sys.stderr)

    registry.skill_count = len(registry.skills)
    return registry


def main():
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent

    registry = generate(root)

    # Write registry.json
    out_json = root / "registry.json"
    out_json.write_text(json.dumps(registry.to_dict(), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {out_json} ({registry.skill_count} skills)")

    # Write llms.txt
    out_llms = root / "llms.txt"
    out_llms.write_text(render_llms_txt(registry))
    print(f"Wrote {out_llms}")


if __name__ == "__main__":
    main()
