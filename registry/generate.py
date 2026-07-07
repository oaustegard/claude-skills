#!/usr/bin/env python3
"""Generate category-based plugins and marketplace.json from SKILL.md frontmatter.

Creates a plugins/ directory with one plugin per category. Each plugin contains
a real copy of each skill directory, following Claude Code's expected structure:

    plugins/<category>/
        .claude-plugin/plugin.json
        skills/
            <skill-name>/SKILL.md   (real files, not a symlink)

The skills are COPIED, not symlinked. GitHub-tree-API importers (Claude Science,
Claude Cowork) walk the committed tree and cannot descend into mode-120000
symlink blobs, so a symlinked plugins/ imports as zero skills. Real files import
everywhere symlinks used to resolve locally. Source of truth remains the
root-level skill directories; plugins/ is a generated artifact.

Usage:
    python registry/generate.py [SKILLS_ROOT]

Defaults to the parent directory of this script (repo root).
"""

import json
import shutil
import sys
from pathlib import Path

# Allow imports from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.frontmatter_utils import parse_skill_md
from registry.schema import Marketplace, PluginEntry

REPO = "oaustegard/claude-skills"
CATEGORIES_FILE = Path(__file__).resolve().parent / "categories.json"


def load_categories() -> dict:
    """Load category definitions from categories.json."""
    with open(CATEGORIES_FILE) as f:
        return json.load(f)["categories"]


def get_skill_version(skill_dir: Path) -> str | None:
    """Extract version from a skill's SKILL.md frontmatter."""
    try:
        fm, _ = parse_skill_md(skill_dir / "SKILL.md")
        meta = fm.get("metadata") or {}
        if meta.get("deprecated"):
            return None
        version = meta.get("version")
        return str(version) if version is not None else None
    except Exception:
        return None


def compute_category_version(skill_dirs: list[Path]) -> str:
    """Compute a category plugin version from its constituent skill versions.

    Uses the highest minor version found across skills, defaulting to 1.0.0.
    """
    max_parts = [1, 0, 0]
    for sd in skill_dirs:
        v = get_skill_version(sd)
        if v:
            try:
                parts = [int(x) for x in v.split(".")[:3]]
                while len(parts) < 3:
                    parts.append(0)
                if parts > max_parts:
                    max_parts = parts
            except ValueError:
                continue
    return ".".join(str(x) for x in max_parts)


def collect_keywords(skill_dir: Path) -> list[str]:
    """Collect keywords from a skill's frontmatter."""
    try:
        fm, _ = parse_skill_md(skill_dir / "SKILL.md")
        meta = fm.get("metadata") or {}
        keywords = []
        deps = meta.get("depends_on")
        if isinstance(deps, list):
            keywords.extend(str(d) for d in deps)
        elif isinstance(deps, str):
            keywords.extend(s.strip() for s in deps.split(",") if s.strip())
        return keywords
    except Exception:
        return []


def _ignore_symlinks(dirpath: str, names: list[str]) -> list[str]:
    """copytree ignore-callback: skip any symlink entries in a source skill dir.

    Skill directories are expected to contain only regular files. A stray
    self-referential symlink (e.g. <skill>/<skill> -> ../../<skill>) would, if
    dereferenced, recurse into the parent; copied as a symlink it would
    reintroduce the mode-120000 blob this generator exists to avoid. Dropping
    symlinks entirely is correct on both counts.
    """
    d = Path(dirpath)
    return [n for n in names if (d / n).is_symlink()]


def build_plugins_dir(root: Path, categories: dict) -> None:
    """Create plugins/ directory with real copies of each skill directory.

    Copies (dereferences) rather than symlinks so the committed tree carries
    actual SKILL.md files under plugins/<cat>/skills/<name>/. See the module
    docstring for why symlinks break tree-API importers.
    """
    plugins_dir = root / "plugins"

    # Full deterministic rebuild: wipe first so skills removed from a category
    # (or moved between categories) leave no stale copies behind. git compares
    # content, so identical regeneration produces an empty diff.
    if plugins_dir.exists():
        shutil.rmtree(plugins_dir)

    for cat_name, cat_info in categories.items():
        cat_dir = plugins_dir / cat_name
        skills_dir = cat_dir / "skills"
        plugin_meta_dir = cat_dir / ".claude-plugin"

        # Create directories
        skills_dir.mkdir(parents=True, exist_ok=True)
        plugin_meta_dir.mkdir(parents=True, exist_ok=True)

        # Copy each skill directory (real files, no symlinks)
        for skill_name in cat_info["skills"]:
            skill_source = root / skill_name
            if not skill_source.exists():
                print(f"WARN: skill directory {skill_name} not found, skipping",
                      file=sys.stderr)
                continue
            if not (skill_source / "SKILL.md").exists():
                print(f"WARN: {skill_name}/SKILL.md not found, skipping",
                      file=sys.stderr)
                continue

            dest = skills_dir / skill_name
            shutil.copytree(skill_source, dest, ignore=_ignore_symlinks)

        # Create plugin.json
        skill_names = [s for s in cat_info["skills"]
                       if (root / s / "SKILL.md").exists()]
        plugin_json = {
            "name": cat_name,
            "description": cat_info["description"],
            "version": compute_category_version(
                [root / s for s in skill_names]
            ),
        }
        (plugin_meta_dir / "plugin.json").write_text(
            json.dumps(plugin_json, indent=2) + "\n"
        )


def build_marketplace(root: Path, categories: dict) -> Marketplace:
    """Build marketplace.json with one plugin entry per category."""
    marketplace = Marketplace()

    for cat_name, cat_info in sorted(categories.items()):
        skill_dirs = [root / s for s in cat_info["skills"]
                      if (root / s / "SKILL.md").exists()]
        if not skill_dirs:
            continue

        # Collect all keywords from constituent skills
        all_keywords: list[str] = []
        for sd in skill_dirs:
            all_keywords.extend(collect_keywords(sd))
        # Add skill names as keywords for discoverability
        all_keywords.extend(sd.name for sd in skill_dirs)
        # Deduplicate preserving order
        seen: set[str] = set()
        unique_keywords: list[str] = []
        for kw in all_keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        entry = PluginEntry(
            name=cat_name,
            description=cat_info["description"],
            source=f"./plugins/{cat_name}",
            version=compute_category_version(skill_dirs),
            homepage=f"https://github.com/{REPO}",
            repository=f"https://github.com/{REPO}",
            license="MIT",
            category=cat_name.replace("-", " ").title(),
            keywords=unique_keywords,
        )
        marketplace.plugins.append(entry)

    return marketplace


def main():
    root = (Path(sys.argv[1]).resolve()
            if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent)

    categories = load_categories()

    # Build plugins/ directory with symlinks
    build_plugins_dir(root, categories)
    print(f"Built plugins/ directory ({len(categories)} category plugins)")

    # Generate marketplace.json
    marketplace = build_marketplace(root, categories)

    out_dir = root / ".claude-plugin"
    out_dir.mkdir(exist_ok=True)

    out_path = out_dir / "marketplace.json"
    out_path.write_text(
        json.dumps(marketplace.to_dict(), indent=2, ensure_ascii=False) + "\n"
    )
    print(f"Wrote {out_path} ({len(marketplace.plugins)} category plugins)")


if __name__ == "__main__":
    main()
