#!/usr/bin/env python3
"""Show which parent-session chunks the context filter would pass for a task.

    python3 preview.py --task "Write the xr latency note for the follow-up memory"
    python3 preview.py --task "..." --task "..." [--budget 20000] [--transcript PATH]

Reads the current session transcript (newest .jsonl under ~/.claude/projects
for this cwd unless --transcript is given), runs the same Jev filter the
PreToolUse hook runs, and prints one line per kept chunk. Exit 1 on a filter
failure, with the reason on stderr: the hook would then pass the prompt through
with no context.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chunking import chunk_transcript  # noqa: E402
import jevfilter as jf  # noqa: E402


def current_transcript(cwd: str) -> str | None:
    slug = cwd.replace("/", "-")
    files = glob.glob(os.path.expanduser(f"~/.claude/projects/{slug}/*.jsonl"))
    return max(files, key=os.path.getmtime) if files else None


def line(c: dict, score: float | None) -> str:
    what = c.get("tool") if c["kind"] == "tool" else c["kind"]
    text = (c.get("text") or c.get("input") or "").replace("\n", " ")
    s = "  --" if score is None else f"{score:4.2f}"
    return f"  [{c['id']:>3}] {s} {what:<14} {jf.clip(text, 90)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", action="append", required=True)
    ap.add_argument("--budget", type=int, default=20_000)
    ap.add_argument("--transcript")
    a = ap.parse_args()
    path = a.transcript or current_transcript(os.getcwd())
    if not path:
        print("no transcript found for this cwd; pass --transcript", file=sys.stderr)
        return 1
    chunks, _ = chunk_transcript(path)
    # Earlier preview calls quote the task verbatim and would rank first.
    chunks = [c for c in chunks if "preview.py" not in (c.get("input") or "")]
    rc = 0
    for task in a.task:
        try:
            ctx, st = jf.build_context(task, chunks, a.budget)
        except jf.FilterError as e:
            print(f"FILTER FAILED for {task[:60]!r}: {e}", file=sys.stderr)
            rc = 1
            continue
        print(f"TASK: {task}\n  keeps {len(st['kept_ids'])} of {len(chunks)} chunks, ~{st['context_tokens']} tokens, "
              f"{st['windows']} window(s), {st['seconds']}s")
        by_id = {c["id"]: c for c in chunks}
        for i in st["kept_ids"]:
            print(line(by_id[i], st["scores"].get(i)))
    return rc


if __name__ == "__main__":
    sys.exit(main())
