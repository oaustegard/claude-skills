#!/usr/bin/env python3
"""On-demand skill discovery over /mnt/skills/user/.

Verbs:
  list                    Print every skill name, one per line.
  search <query>          Print ranked name+description matches (tab-separated).
  show <name>             Print full SKILL.md for <name> to stdout.

Exit codes:
  0 success
  1 skill not found (show)
  2 invalid usage
"""
from __future__ import annotations

import os
import pathlib
import re
import signal
import sys
from typing import Iterator

# Restore default SIGPIPE handling so piping into `head` etc. exits cleanly.
if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

SKILLS_DIR = pathlib.Path(os.environ.get("SKILLS_DIR", "/mnt/skills/user"))
DESC_TRUNCATE = 200


def _iter_skills() -> Iterator[tuple[str, pathlib.Path]]:
    if not SKILLS_DIR.is_dir():
        return
    for entry in sorted(SKILLS_DIR.iterdir()):
        skill_md = entry / "SKILL.md"
        if skill_md.is_file():
            yield entry.name, skill_md


def _parse_meta(path: pathlib.Path) -> tuple[str | None, str | None]:
    """Return (name, description) from a SKILL.md's YAML frontmatter.

    description may span multiple lines — we capture until the next
    top-level YAML key or the closing '---'.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, None

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not fm_match:
        return None, None
    frontmatter = fm_match.group(1)

    name = None
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.M)
    if name_match:
        name = name_match.group(1).strip()

    desc = None
    desc_match = re.search(
        r"^description:\s*(.+?)(?=^\S|^\s*$)",
        frontmatter,
        re.M | re.S,
    )
    if desc_match:
        desc = " ".join(desc_match.group(1).split())

    return name, desc


def cmd_list() -> int:
    for name, _ in _iter_skills():
        print(name)
    return 0


def cmd_search(query: str) -> int:
    q = query.lower().strip()
    if not q:
        print("search: empty query", file=sys.stderr)
        return 2

    hits: list[tuple[int, str, str]] = []
    for name, path in _iter_skills():
        parsed_name, desc = _parse_meta(path)
        display_name = parsed_name or name
        score = 0
        name_lower = name.lower()
        if q == name_lower:
            score += 100
        elif q in name_lower:
            score += 10
        if desc:
            score += desc.lower().count(q)
        if score > 0:
            hits.append((score, display_name, desc or ""))

    hits.sort(key=lambda h: (-h[0], h[1]))
    for _, display_name, desc in hits:
        truncated = desc if len(desc) <= DESC_TRUNCATE else desc[:DESC_TRUNCATE] + "…"
        print(f"{display_name}\t{truncated}")
    return 0


def cmd_show(name: str) -> int:
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.is_file():
        print(f"skill not found: {name}", file=sys.stderr)
        return 1
    sys.stdout.write(path.read_text(encoding="utf-8", errors="replace"))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    verb = argv[1]
    rest = argv[2:]
    if verb == "list" and not rest:
        return cmd_list()
    if verb == "search" and rest:
        return cmd_search(" ".join(rest))
    if verb == "show" and len(rest) == 1:
        return cmd_show(rest[0])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
