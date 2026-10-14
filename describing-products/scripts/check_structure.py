#!/usr/bin/env python3
"""Check the mechanical half of the consistency pass on a product description repo.

Usage: python3 check_structure.py [repo-root] [--reference area/pilot.md] [--exclude PATH ...]

Feature documents are every .md file except the root's README.md, goal.md,
glossary.md, AGENTS.md, CLAUDE.md, bug-triage.md, and anything under
verification/, and any path given to --exclude (a RESULTS.md or CHANGELOG.md the
host repo's conventions require). For them it checks:

  coverage   every feature document is a row in README.md's "## Coverage"
             table, every row past `not started` exists on disk, and every
             status is `not started`, `drafted` or `verified`
  sections   the template's H2 sections that a document has are in template
             order, and "## Open questions and verification" is last and ends
             with a `Verified against ... commit `sha`` footer
  tables     the "Modifiers" and "Cancel and interrupt" tables have the same
             rows, in the same order, as the reference document, and no empty
             cell; a document with "The interaction, event by event" has both
  concerns   the bold-led paragraphs under "Interactions with other systems"
             name the same concerns in the same order as the reference

The reference is --reference (the pilot) when given, else the most common
shape among the documents. Documents citing different source commits are
reported as a warning, since the skill allows it only when the footer says so.
Exits 1 on any error; warnings alone exit 0.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

NON_FEATURE = {"README.md", "goal.md", "glossary.md", "AGENTS.md", "CLAUDE.md", "bug-triage.md"}
SECTIONS = [
    "summary",
    "the simple case",
    "the interaction, event by event",
    "modifiers",
    "cancel and interrupt",
    "interactions with other systems",
    "edge cases",
    "open questions and verification",
]
STATUSES = {"not started", "drafted", "verified"}
FOOTER = re.compile(r"Verified against .+? commit `([0-9a-f]{7,40})`")
FENCE = re.compile(r"^\s*(```|~~~)")
BOLD_LEAD = re.compile(r"^\*\*(.+?)\*\*")
MD_PATH = re.compile(r"([\w./-]+\.md)")


def feature_docs(root: Path, exclude: frozenset[str] = frozenset()) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        if rel.as_posix() in exclude:
            continue
        if any(part.startswith(".") or part == "node_modules" for part in rel.parts):
            continue
        if rel.parts[0] == "verification":
            continue
        if len(rel.parts) == 1 and rel.name in NON_FEATURE:
            continue
        out.append(p)
    return out


def sections(text: str) -> dict[str, list[str]]:
    """Map each lowercased H2 title to its body lines, ignoring fenced code."""
    result: dict[str, list[str]] = {}
    current: str | None = None
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            current = line[3:].strip().lower()
            result[current] = []
        elif current is not None:
            result[current].append(line)
    return result


def table_rows(lines: list[str]) -> list[list[str]]:
    """Cells of the first markdown table in `lines`, header and divider dropped."""
    rows: list[list[str]] = []
    started = False
    for line in lines:
        if line.lstrip().startswith("|"):
            started = True
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            rows.append(cells)
        elif started:
            break
    body = rows[2:] if len(rows) >= 2 and set("".join(rows[1])) <= set("-: ") else rows[1:]
    return body


def bold_leads(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        m = BOLD_LEAD.match(line.strip())
        if m:
            out.append(m.group(1).strip().rstrip(".:").lower())
    return out


def coverage_rows(readme: Path) -> list[tuple[str, str]] | None:
    if not readme.exists():
        return None
    sec = sections(readme.read_text(encoding="utf-8")).get("coverage")
    if sec is None:
        return None
    rows = []
    for cells in table_rows(sec):
        if len(cells) < 2:
            continue
        m = MD_PATH.search(cells[0].replace("`", ""))
        if m:
            rows.append((m.group(1), cells[1].strip("` ").lower()))
    return rows


def check(root: Path, reference: Path | None,
          exclude: frozenset[str] = frozenset()) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    docs = feature_docs(root, exclude)

    cov = coverage_rows(root / "README.md")
    if cov is None:
        errors.append("README.md: no '## Coverage' table")
    else:
        listed = {path for path, _ in cov}
        for path, status in cov:
            if status not in STATUSES:
                errors.append(f"README.md coverage: {path}: unknown status '{status}'")
            if status != "not started" and not (root / path).exists():
                errors.append(f"README.md coverage: {path} is '{status}' but missing on disk")
        for d in docs:
            rel = d.relative_to(root).as_posix()
            if rel not in listed:
                errors.append(f"{rel}: on disk but not in the README coverage table")

    parsed = {d: sections(d.read_text(encoding="utf-8")) for d in docs}
    shapes: dict[str, dict[Path, tuple[str, ...]]] = {"modifiers": {}, "cancel and interrupt": {}, "concerns": {}}
    commits: dict[str, list[str]] = {}

    for d, secs in parsed.items():
        rel = d.relative_to(root).as_posix()
        present = [s for s in secs if s in SECTIONS]
        if present != sorted(present, key=SECTIONS.index):
            errors.append(f"{rel}: sections out of template order: {present}")
        if "open questions and verification" not in secs:
            errors.append(f"{rel}: no '## Open questions and verification' section")
        else:
            if list(secs)[-1] != "open questions and verification":
                errors.append(f"{rel}: 'Open questions and verification' is not the last section")
            m = FOOTER.search("\n".join(secs["open questions and verification"]))
            if m:
                commits.setdefault(m.group(1), []).append(rel)
            else:
                errors.append(f"{rel}: no 'Verified against ... commit `sha`' footer")
        if "the interaction, event by event" in secs:
            for need in ("modifiers", "cancel and interrupt"):
                if need not in secs:
                    errors.append(f"{rel}: has an interaction but no '## {need.capitalize()}' table")
        for name in ("modifiers", "cancel and interrupt"):
            if name not in secs:
                continue
            rows = table_rows(secs[name])
            if not rows:
                errors.append(f"{rel}: '## {name.capitalize()}' has no table")
                continue
            for r in rows:
                if any(c == "" for c in r):
                    errors.append(f"{rel}: {name} row '{r[0]}' has an empty cell")
            shapes[name][d] = tuple(r[0].lower() for r in rows)
        if "interactions with other systems" in secs:
            shapes["concerns"][d] = tuple(bold_leads(secs["interactions with other systems"]))

    for name, by_doc in shapes.items():
        if not by_doc:
            continue
        if reference is not None and reference in by_doc:
            want, source = by_doc[reference], reference.relative_to(root).as_posix()
        else:
            want = Counter(by_doc.values()).most_common(1)[0][0]
            source = "the most common shape"
        for d, got in by_doc.items():
            if got != want:
                rel = d.relative_to(root).as_posix()
                missing = [x for x in want if x not in got]
                extra = [x for x in got if x not in want]
                detail = []
                if missing:
                    detail.append(f"missing {missing}")
                if extra:
                    detail.append(f"extra {extra}")
                if not detail:
                    detail.append("same rows, different order")
                errors.append(f"{rel}: {name} differs from {source}: {'; '.join(detail)}")

    if len(commits) > 1:
        summary = ", ".join(f"{sha} ({len(files)} docs)" for sha, files in sorted(commits.items()))
        warnings.append(f"documents cite {len(commits)} source commits: {summary}")
    return errors, warnings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--reference", help="the pilot document, relative to root")
    ap.add_argument("--exclude", action="append", default=[],
                    help="a non-feature .md file, relative to root (repeatable)")
    args = ap.parse_args()
    root = Path(os.path.abspath(args.root))
    ref = (root / args.reference) if args.reference else None
    if ref is not None and not ref.exists():
        sys.exit(f"--reference {args.reference}: no such file under {root}")
    exclude = frozenset(Path(e).as_posix() for e in args.exclude)
    errors, warnings = check(root, ref, exclude)
    for e in errors:
        print(f"error: {e}")
    for w in warnings:
        print(f"warning: {w}")
    print(f"{len(feature_docs(root, exclude))} feature documents, {len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
