"""Stand-in for headless_fanout.py + a model child, for testing the machinery (--fake).

    python3 fake_worker.py TASK.jsonl --work DIR --cwd WORKTREE [--mode MODE]

Writes what the real runner would: DIR/ledger.jsonl (cost 0) and the task's out
JSON. The task's "fake" entry names the project's code dir, a forbidden dir and
an allowed best-effort file. Modes (default $SWARM_FAKE_MODE, else "fix"; a
"[fake:MODE]" tag in the prompt overrides per task):
  fix       create <code>/_fake_fixes/<suite>__<name> per representative test; the
            selftest's fake test command treats that file as "this test now passes"
  noop      change nothing, report failed
  break     like fix, but also delete one existing fix marker (a regression)
  tests     edit a file under the forbidden dir (the gate must reject it)
  conflict  like fix, plus write <code>/_fake_conflict.txt (two of these conflict)
  docs      like fix, plus write the allowed file (two of these conflict on docs only)
  syntax    like fix, plus a .py under <code> that does not compile (compat gate rejects it)
  shared    write <code>/_fake_fixes/_all_<suite>: one root-cause fix for a whole suite
  latin1    like fix, plus a file of non-UTF-8 bytes (the diff must round-trip, not crash the loop)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_BLOCK = re.compile(r"^<{7} [^\n]*\n(.*?)^={7}\n(.*?)^>{7} [^\n]*\n", re.MULTILINE | re.DOTALL)


def resolve_markers(cwd: Path) -> list[str]:
    """Resolve git-apply --3way conflict blocks by keeping both sides, as the rebase prompt asks."""
    names = subprocess.run(["git", "-C", str(cwd), "diff", "--name-only"],
                           capture_output=True, text=True, check=False).stdout.split()
    fixed = []
    for n in names:
        p = cwd / n
        if p.is_file():
            s = p.read_text(errors="replace")
            if "<<<<<<< " in s:
                p.write_text(_BLOCK.sub(lambda m: m.group(1) + m.group(2), s))
                fixed.append(n)
    return fixed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", type=Path)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--cwd", type=Path, required=True)
    ap.add_argument("--mode", default=os.environ.get("SWARM_FAKE_MODE", "fix"))
    a, _ = ap.parse_known_args(argv)
    task = json.loads(a.tasks.read_text().splitlines()[0])
    fk = task.get("fake") or {}
    code = fk.get("code", "src/").rstrip("/")
    tests = re.findall(r"^  - (\S+)", task["prompt"], re.MULTILINE)
    mode = a.mode
    m = re.search(r"\[fake:(\w+)\]", task["prompt"])
    if m:
        mode = m.group(1)
    time.sleep(0.5)
    fixdir = a.cwd / code / "_fake_fixes"
    changed = resolve_markers(a.cwd)   # a REBASE task starts from a conflicted tree; a real worker resolves it
    if mode == "conflict":
        (a.cwd / code / "_fake_conflict.txt").write_text(task["id"] + "\n")
        changed.append(f"{code}/_fake_conflict.txt")
    if mode == "docs":
        p = a.cwd / fk.get("allowed", "docs/NOTES.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"done by {task['id']}\n")
        changed.append(str(p.relative_to(a.cwd)))
    if mode == "shared" and tests:
        fixdir.mkdir(parents=True, exist_ok=True)
        p = fixdir / f"_all_{tests[0].split('/', 1)[0]}"
        p.write_text("fixed\n")
        changed.append(str(p.relative_to(a.cwd)))
    if mode == "latin1":
        (a.cwd / code / "_fake_latin1.txt").write_bytes(b"caf\xe9 \xff\n")
        changed.append(f"{code}/_fake_latin1.txt")
    if mode in ("fix", "break", "conflict", "docs", "syntax", "latin1"):
        fixdir.mkdir(parents=True, exist_ok=True)
        for t in tests:
            p = fixdir / t.replace("/", "__")
            p.write_text("fixed\n")
            changed.append(str(p.relative_to(a.cwd)))
    if mode == "break":
        others = sorted(x for x in fixdir.iterdir() if str(x.relative_to(a.cwd)) not in changed)
        if others:
            others[0].unlink()
            changed.append(str(others[0].relative_to(a.cwd)))
    if mode == "syntax":
        (a.cwd / code / "_fake_bad.py").write_text("def broken(:\n    pass\n")
        changed.append(f"{code}/_fake_bad.py")
    if mode == "tests":
        p = a.cwd / fk.get("forbidden", "tests/").rstrip("/") / "HACK.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("cheating\n")
        changed.append(str(p.relative_to(a.cwd)))
    scratch = re.search(r"^Scratch dir: (\S+)", task["prompt"], re.MULTILINE)
    if scratch:    # leave scratch behind like a real worker does; reap must delete it
        Path(scratch.group(1)).mkdir(parents=True, exist_ok=True)
        (Path(scratch.group(1)) / "t.c").write_text("scratch\n")
    status = {"noop": "failed", "stale": "stale"}.get(mode, "fixed")
    out = {"status": status, "test_ids_fixed": tests if status == "fixed" else [],
           "files_changed": changed, "root_cause": f"fake {mode}: {', '.join(tests)}"[:72],
           "notes": f"fake worker mode={mode}"}
    Path(task["out"]).parent.mkdir(parents=True, exist_ok=True)
    Path(task["out"]).write_text(json.dumps(out))
    a.work.mkdir(parents=True, exist_ok=True)
    (a.work / "results").mkdir(exist_ok=True)
    (a.work / "results" / f"{task['id']}.json").write_text(json.dumps({"total_cost_usd": 0.0, "result": "fake"}))
    with (a.work / "ledger.jsonl").open("a") as f:
        f.write(json.dumps({"id": task["id"], "attempt": 1, "ok": True, "reason": None, "cost": 0.0,
                            "secs": 0.5, "turns": 1, "denials": 0}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
