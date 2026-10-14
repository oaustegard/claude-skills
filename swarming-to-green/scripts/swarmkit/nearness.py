"""Near-hold: don't dispatch a rebase while a live worker edits the files it will touch.

A rebase task re-applies a conflicted patch, so the files it will edit are known before it
starts. If a worker in flight (or a finished candidate waiting for the gate) is changing one
of those files, the rebase will probably conflict again when that worker merges. Hold it,
dispatch other work, and launch it once the near peers have landed or `near_hold_s` has
passed since the conflict (the cap keeps a hot file from starving it).

Backtest on the haiku-cc sibling ledgers (experiments/nearness-lanes): of 54 rebase tasks
that reached the gate, 43 had a live near peer at launch and 31 of them (72%) conflicted
again; 1 of the other 11 did. First attempts get no hold: nothing at dispatch (signature,
stage) predicted their files, and file nearness is only a proxy for what git already
answers at the gate.

Only files the patch modifies count. A new file cannot collide except add/add.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from swarmkit.common import Ctx, is_conflict


def patch_files(patch: str) -> set[str]:
    """Files a unified diff modifies, deletes or renames from; new files are left out."""
    out: set[str] = set()
    cur, new = None, False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            if cur and not new:
                out.add(cur)
            parts = line.split(" b/", 1)
            cur, new = (parts[0][len("diff --git a/"):] if len(parts) == 2 else None), False
        elif line.startswith("new file mode"):
            new = True
    if cur and not new:
        out.add(cur)
    return out


def pending_rebase(ctx: Ctx, led: dict, signature: str) -> dict | None:
    """The conflicted record the next worker on `signature` would rebase, or None."""
    used = {r.get("rebase_of") for r in led.values()}
    conflicted = [r for r in led.values() if r.get("signature") == signature and is_conflict(r)
                  and r["id"] not in used and (ctx.task_dir(r["id"]) / "patch.diff").exists()]
    return conflicted[-1] if conflicted else None


def _worktree_files(wt: Path, base: str) -> set[str] | None:
    p = subprocess.run(["git", "-C", str(wt), "diff", "--name-only", "--diff-filter=MDR", base],
                       capture_output=True, text=True, check=False)
    return set(p.stdout.split()) if p.returncode == 0 else None


def live_files(ctx: Ctx, led: dict) -> dict[str, set[str]]:
    """{task id: files it is changing} for workers in flight and candidates waiting for the gate."""
    out: dict[str, set[str]] = {}
    for r in led.values():
        if r.get("status") == "launched":
            wt = ctx.worktree(r["id"])
            files = _worktree_files(wt, r["base"]) if wt.exists() else None
        elif r.get("status") == "finished":
            p = ctx.task_dir(r["id"]) / "patch.diff"
            files = patch_files(p.read_text(errors="replace")) if p.exists() else \
                set((r.get("result") or {}).get("files_changed") or [])
        else:
            continue
        if files:
            out[r["id"]] = files
    return out


def hold(ctx: Ctx, led: dict, signature: str, live: dict[str, set[str]], now: float | None = None) -> list[str]:
    """Ids of live peers that should make the next worker on `signature` wait ([] = dispatch).
    `live` is live_files(), computed once per dispatch round."""
    cap = ctx.cfg["queue"].get("near_hold_s", 0)
    if not cap:
        return []
    src = pending_rebase(ctx, led, signature)
    if src is None:
        return []
    since = src.get("t_gate") or src.get("t_done") or src.get("t_launch") or 0
    if (now or time.time()) - since > cap:
        return []
    mine = patch_files((ctx.task_dir(src["id"]) / "patch.diff").read_text(errors="replace"))
    return sorted(tid for tid, files in live.items() if tid != src["id"] and files & mine)
