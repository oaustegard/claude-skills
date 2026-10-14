"""Tests for check_links.py and check_structure.py. Run: pytest describing-products/scripts"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_links
import check_structure

DOC = """# The {name}

## Summary

S.

## The interaction, event by event

I.

## Modifiers

| Modifier | Set at the start | Changed while extended |
| --- | --- | --- |
| Shift | No effect. | No effect. |
| Alt | {alt} | No effect. |

## Cancel and interrupt

| Event | Before | While |
| --- | --- | --- |
{cancel}

## Interactions with other systems

**Permissions.** None.

**History.** One undo step.

## Open questions and verification

- Nothing.

Verified against app commit `{sha}`.
"""
CANCEL = "| Escape | Ends. | Ends. |\n| Focus lost | Ends. | Ends. |"
README = """# X

## Coverage

| Document | Status |
| --- | --- |
| glossary.md | drafted |
| tools/a.md | drafted |
| tools/b.md | drafted |
| tools/c.md | not started |
"""


def write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def doc(name: str, alt: str = "Copies.", cancel: str = CANCEL, sha: str = "abc1234") -> str:
    return DOC.format(name=name, alt=alt, cancel=cancel, sha=sha)


def test_links_slugs_match_github(tmp_path: Path) -> None:
    write(tmp_path, {"a.md": (
        "# T\n\n## The snake_case flag\n\n## Café rules\n\n## Step 1. Setup\n\n## *Bold* _it_\n\n"
        "[a](#the-snake_case-flag) [b](#café-rules) [c](#step-1-setup) [d](#bold-it)\n")})
    problems, _, _, checked = check_links.check(str(tmp_path))
    assert checked == 4
    assert problems == []


def test_links_ignore_code_and_check_reference_defs(tmp_path: Path) -> None:
    write(tmp_path, {"a.md": (
        "Write `[text](missing.md)` like this.\n\n```\n[x](gone.md)\n```\n\n"
        "See [r][ref] and [ok](b.md#top).\n\n[ref]: nowhere.md\n"),
        "b.md": "# Top\n"})
    problems, _, _, _ = check_links.check(str(tmp_path))
    assert problems == ["a.md:9: missing file: nowhere.md"]


def test_structure_clean_repo_passes(tmp_path: Path) -> None:
    write(tmp_path, {"README.md": README, "glossary.md": "# G\n",
                     "tools/a.md": doc("a"), "tools/b.md": doc("b")})
    errors, warnings = check_structure.check(tmp_path, None)
    assert errors == [] and warnings == []


def test_structure_catches_drift(tmp_path: Path) -> None:
    write(tmp_path, {
        "README.md": README.replace("| tools/b.md | drafted |\n", ""),
        "glossary.md": "# G\n",
        "tools/a.md": doc("a"),
        "tools/b.md": doc("b", alt="", cancel="| Focus lost | Ends. | Ends. |\n| Escape | Ends. | Ends. |",
                          sha="def5678"),
        "tools/d.md": doc("d"),
    })
    errors, warnings = check_structure.check(tmp_path, tmp_path / "tools/a.md")
    text = "\n".join(errors)
    assert "tools/b.md: on disk but not in the README coverage table" in text
    assert "tools/d.md: on disk but not in the README coverage table" in text
    assert "tools/b.md: modifiers row 'Alt' has an empty cell" in text
    assert "tools/b.md: cancel and interrupt differs from tools/a.md: same rows, different order" in text
    assert warnings and "2 source commits" in warnings[0]


def test_structure_missing_footer_and_sections(tmp_path: Path) -> None:
    broken = doc("a").replace("Verified against app commit `abc1234`.", "").replace(
        "## Cancel and interrupt", "## Not the cancel section")
    write(tmp_path, {"README.md": README.replace("tools/b.md | drafted", "tools/b.md | not started"),
                     "tools/a.md": broken})
    errors, _ = check_structure.check(tmp_path, None)
    text = "\n".join(errors)
    assert "tools/a.md: no 'Verified against ... commit `sha`' footer" in text
    assert "has an interaction but no '## Cancel and interrupt' table" in text
    assert "glossary.md" in text  # listed as drafted, missing on disk


def test_links_to_planned_documents_are_not_broken(tmp_path: Path) -> None:
    write(tmp_path, {"README.md": README, "tools/a.md": "See [c](c.md) and [gone](gone.md).\n"})
    problems, planned, _, _ = check_links.check(str(tmp_path))
    assert problems == ["tools/a.md:1: missing file: gone.md"]
    assert planned == ["tools/a.md:1: planned: c.md"]
    strict, planned, _, _ = check_links.check(str(tmp_path), strict=True)
    assert len(strict) == 2 and planned == []


def test_structure_exclude(tmp_path: Path) -> None:
    write(tmp_path, {"README.md": README, "glossary.md": "# G\n", "tools/a.md": doc("a"),
                     "tools/b.md": doc("b"), "RESULTS.md": "# Results\n"})
    errors, _ = check_structure.check(tmp_path, None)
    assert any("RESULTS.md" in e for e in errors)
    errors, _ = check_structure.check(tmp_path, None, frozenset({"RESULTS.md"}))
    assert errors == []
