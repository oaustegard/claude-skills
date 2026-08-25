#!/usr/bin/env python3
"""Run the skill spec check over this repo, scoped to what a branch changed.

    validate_skills.py --changed-vs origin/main     # gate: only what this PR touched
    validate_skills.py --all                        # audit: whole catalogue
    validate_skills.py exploring-codebases flowing  # named skills

Exits 1 if any selected skill fails. The check itself is Anthropic's
`quick_validate.py`, vendored under scripts/vendor/ so CI runs the same rules
that gate an actual upload: YAML parseability, the allowed-property whitelist,
kebab-case names, the 64/1024 length caps, no angle brackets anywhere, and
exactly one SKILL.md per skill directory.

WHY DIFF-SCOPED BY DEFAULT

A whole-tree gate on a catalogue with pre-existing violations is red on arrival,
and a check that is always red gets ignored. `controlling-spotify` carries
`credentials` and `domains` keys outside the allowed set; whether those keys have
a live consumer is not something CI should decide. So the PR gate asks only "did
this branch add a violation", and `--all` stays available for the audit. Same
split as `muninn_utils.ruff_gate` in claude-workspace, for the same reason.

Diagnosed 2026-08-24 and 2026-08-25: an unquoted ": " inside a long description
ends the YAML scalar, and an angle bracket is rejected outright. Either way the
skill stops loading, silently, while a regex-based reader still ranks it happily.
Four such violations were live in this repo before anyone ran the check.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
from quick_validate import validate_skill  # noqa: E402


def all_skills() -> list[Path]:
    return sorted(p.parent for p in REPO.glob("*/SKILL.md"))


def changed_skills(ref: str) -> list[Path]:
    """Skill dirs whose SKILL.md differs from `ref`.

    Uses `ref...HEAD` so the comparison is against the merge base, not the tip
    of the base branch — otherwise every unrelated commit landing on main while
    a PR is open reads as this branch's change. A deleted skill has nothing to
    validate, so filter to dirs that still exist rather than failing on a rename.

    This compares COMMITS. An uncommitted edit in the working tree is invisible
    here, which is right for CI (a PR branch always has its changes committed)
    and a trap locally: `--changed-vs` on a dirty tree reports "nothing to
    validate". Commit first, or name the skill directly.
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{ref}...HEAD"],
            cwd=REPO, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"git diff against {ref!r} failed: {e.stderr.strip()}") from e
    dirs = {REPO / line.split("/")[0] for line in out.splitlines()
            if line.endswith("/SKILL.md") and line.count("/") == 1}
    return sorted(d for d in dirs if (d / "SKILL.md").exists())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("skills", nargs="*", help="skill directory names")
    ap.add_argument("--all", action="store_true", help="validate every skill")
    ap.add_argument("--changed-vs", metavar="REF",
                    help="validate only skills this branch changed vs REF")
    ap.add_argument("--warn-only", action="store_true",
                    help="report failures but exit 0 (for informational audits)")
    args = ap.parse_args()

    if args.all:
        targets = all_skills()
        scope = f"all {len(targets)} skills"
    elif args.changed_vs:
        targets = changed_skills(args.changed_vs)
        scope = f"{len(targets)} skill(s) changed vs {args.changed_vs}"
    elif args.skills:
        targets = [REPO / s for s in args.skills]
        scope = f"{len(targets)} named skill(s)"
    else:
        ap.error("pass --all, --changed-vs REF, or one or more skill names")

    if not targets:
        print(f"No SKILL.md changed vs {args.changed_vs} — nothing to validate.")
        return

    print(f"Validating {scope}\n")
    bad = []
    for d in targets:
        if not (d / "SKILL.md").exists():
            bad.append((d.name, "SKILL.md not found"))
            print(f"  FAIL  {d.name}: SKILL.md not found")
            continue
        ok, msg = validate_skill(d)
        if ok:
            print(f"  ok    {d.name}")
        else:
            bad.append((d.name, msg))
            print(f"  FAIL  {d.name}: {msg}")

    print()
    if not bad:
        print(f"All {len(targets)} valid.")
        return
    print(f"{len(bad)} of {len(targets)} invalid:")
    for name, msg in bad:
        print(f"  {name}: {msg.splitlines()[0]}")
    if args.warn_only:
        print("\n(--warn-only: not failing the build)")
        return
    sys.exit(1)


if __name__ == "__main__":
    main()
