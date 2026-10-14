#!/usr/bin/env python3
"""Check relative links and heading anchors across a product description repo.

Usage: python3 check_links.py [repo-root] [--strict]   (default root: current directory)

Walks every .md file and checks every inline link `[text](target)` and every
reference definition `[label]: target`. Reports targets whose file does not
exist, or whose `#anchor` matches no heading (or `<a id/name>`) in the target
file. Skips URLs with a scheme (http:, mailto:), fenced code blocks, and inline
code spans. Exits 1 if anything is broken.

A link to a missing file that README.md's "## Coverage" table lists as
`not started` is a link to a planned document, not a broken one: a repo built
in phases links to foundations and siblings before they exist. Those are
listed separately and do not fail the run unless --strict is given, which is
what the final consistency pass uses.

Slugs follow GitHub's rule (github-slugger): lowercase; drop punctuation but
keep letters in any script, digits, `_`, `-` and spaces; each space becomes a
hyphen; repeats get -1, -2, ... Accented letters are kept as they are, not
folded to ASCII, because GitHub keeps them.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterator

INLINE_LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s>]+)>?")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ANCHOR = re.compile(r"<a\s+[^>]*(?:id|name)=\"([^\"]+)\"", re.IGNORECASE)
FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def slugify(text: str) -> str:
    """Return GitHub's anchor slug for a heading's source text."""
    text = CODE_SPAN.sub(lambda m: m.group(2), text)          # keep code text, drop ticks
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)     # keep link text only
    text = re.sub(r"<[^>]+>", "", text)                        # drop inline HTML
    text = text.replace("*", "")
    text = re.sub(r"(?<![\w])_+|_+(?![\w])", "", text)         # emphasis underscores only
    text = text.lower()
    text = "".join(ch for ch in text if ch.isalnum() or ch in " -_")
    return text.replace(" ", "-")


def strip_code(lines: list[str]) -> list[str]:
    """Blank out fenced blocks and inline code spans, keeping line numbers."""
    out, in_fence = [], False
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else CODE_SPAN.sub("", line))
    return out


def anchors_of(path: str) -> set[str]:
    """All anchors a link into `path` may target."""
    with open(path, encoding="utf-8") as f:
        raw = f.read().splitlines()
    seen: dict[str, int] = {}
    slugs: set[str] = set()
    in_fence = False
    for line in raw:
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        slugs.update(a.lower() for a in HTML_ANCHOR.findall(line))
        m = HEADING.match(line)
        if not m:
            continue
        base = slugify(m.group(2))
        n = seen.get(base, 0)
        seen[base] = n + 1
        slugs.add(base if n == 0 else f"{base}-{n}")
    return slugs


def md_files(root: str) -> Iterator[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        for name in filenames:
            if name.endswith(".md"):
                yield os.path.join(dirpath, name)


def targets_in(line: str) -> list[str]:
    found = INLINE_LINK.findall(line)
    m = REF_DEF.match(line)
    if m:
        found.append(m.group(1))
    return found


def planned_docs(root: str) -> set[str]:
    """Absolute paths the README coverage table lists as `not started`."""
    readme = os.path.join(root, "README.md")
    if not os.path.exists(readme):
        return set()
    with open(readme, encoding="utf-8") as f:
        lines = f.read().splitlines()
    planned: set[str] = set()
    in_coverage = False
    for line in lines:
        if line.startswith("## "):
            in_coverage = line[3:].strip().lower() == "coverage"
            continue
        if not in_coverage or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1].lower() == "not started":
            m = re.search(r"[\w./-]+\.md", cells[0])
            if m:
                planned.add(os.path.normpath(os.path.join(root, m.group(0))))
    return planned


def check(root: str, strict: bool = False) -> tuple[list[str], list[str], int, int]:
    """Return (problems, links to planned documents, files checked, links checked)."""
    files = sorted(md_files(root))
    anchors: dict[str, set[str]] = {}
    problems: list[str] = []
    planned_links: list[str] = []
    planned = set() if strict else planned_docs(root)
    checked = 0
    for path in files:
        with open(path, encoding="utf-8") as f:
            lines = strip_code(f.read().splitlines())
        rel = os.path.relpath(path, root)
        for lineno, line in enumerate(lines, 1):
            for target in targets_in(line):
                if SCHEME.match(target):
                    continue
                checked += 1
                file_part, _, anchor = target.partition("#")
                dest = (os.path.normpath(os.path.join(os.path.dirname(path), file_part))
                        if file_part else path)
                if not os.path.exists(dest):
                    if dest in planned:
                        planned_links.append(f"{rel}:{lineno}: planned: {target}")
                    else:
                        problems.append(f"{rel}:{lineno}: missing file: {target}")
                    continue
                if anchor and dest.endswith(".md"):
                    if dest not in anchors:
                        anchors[dest] = anchors_of(dest)
                    if anchor.lower() not in anchors[dest]:
                        problems.append(f"{rel}:{lineno}: missing anchor: {target}")
    return problems, planned_links, len(files), checked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--strict", action="store_true",
                    help="treat links to `not started` documents as broken")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    problems, planned_links, n_files, n_links = check(root, args.strict)
    for p in problems + planned_links:
        print(p)
    print(f"{n_files} files, {n_links} relative links, {len(problems)} broken, "
          f"{len(planned_links)} to planned documents")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
