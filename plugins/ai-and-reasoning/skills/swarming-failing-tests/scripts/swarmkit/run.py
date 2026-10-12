"""Swarm main loop: baseline -> queue -> workers -> merge gate -> repeat.

Each worker is one `headless_fanout.py run` process (dispatching-subagents) with a
one-task tasks.jsonl, --cwd set to its own worktree (wt_root/<task id>, detached at
main HEAD), the configured tools, and write rules for its worktree and scratch dir.
Its result JSON goes to wt_root/_results/<id>.json.

Resumable: everything lives in the state dir. On restart, workers whose process
is still alive are adopted, dead ones are reaped, finished ones are gated, and
commits that reached main before a crash are reconciled into the ledger.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

from swarmkit import federation as fed
from swarmkit import merge, workqueue
from swarmkit import testrun as tr
from swarmkit.common import (
    SCHEMA,
    Ctx,
    add_worktree,
    attempt_epoch,
    event,
    find_fanout,
    free_gb,
    git,
    head,
    is_conflict,
    ledger,
    ledger_put,
    log,
    quarantined,
    read_json,
    read_jsonl,
    remove_worktree,
    write_json,
)
from swarmkit.config import resolve

FAKE_WORKER = Path(__file__).resolve().parent / "fake_worker.py"


# ---------------------------------------------------------------- launching

def source_size(ctx: Ctx):
    root = resolve(ctx.root, ctx.tests["source_root"]) if ctx.tests["source_root"] else None

    def size(test_id: str) -> int:
        if root is None:
            return 0
        suite, _, rel = test_id.partition("/")
        try:
            return (root / suite / rel).stat().st_size
        except OSError:
            return 10 ** 9
    return size


def premerge_rebase(wt: Path, patch: str, code_dirs: list[str]) -> list[str] | None:
    """Re-apply a conflicted worker's diff into a fresh worktree with `git apply --3way`, leaving
    conflict markers in place for the rebase worker to resolve. Returns the conflicted files ([] when
    it applied cleanly), or None when it could not be applied at all (the worker re-applies by hand)."""
    p = subprocess.run(["git", "-C", str(wt), "apply", "--3way", "--whitespace=nowarn", patch],
                       capture_output=True, text=True, check=False)
    unmerged = subprocess.run(["git", "-C", str(wt), "diff", "--name-only", "--diff-filter=U"],
                              capture_output=True, text=True, check=False).stdout.split()
    if p.returncode != 0 and not unmerged:
        subprocess.run(["git", "-C", str(wt), "checkout", "--", "."], capture_output=True, check=False)
        for d in code_dirs:
            subprocess.run(["git", "-C", str(wt), "clean", "-fdq", "--", d], capture_output=True, check=False)
        return None
    # Leave conflicted files as plain working-tree edits: the orchestrator diffs with `git add -A`.
    subprocess.run(["git", "-C", str(wt), "reset", "-q"], capture_output=True, check=False)
    return unmerged


def task_prompt(ctx: Ctx, tid: str, item: workqueue.WorkItem, out: Path, prev_notes: list[str],
                feature: bool, rebase_patch: str | None = None, conflicted_files: list[str] | None = None) -> str:
    w = ctx.worker
    scratch = ctx.scratch(tid)
    lines = [f"Task id: {tid}", f"Your worktree (current directory): {ctx.worktree(tid)}",
             f"Result JSON out path: {out}", f"Scratch dir: {scratch}/", "",
             f"Failure cluster: {item.signature}", f"({item.size} failing tests share this signature)", "",
             "Representative tests to fix:"]
    for t in item.tests:
        lines += [f"  - {t}", f"    reason: {item.reasons.get(t, '')}"]
        if w["repro_command"]:
            lines.append("    run: " + w["repro_command"].format(suite=t.split("/", 1)[0], test=t))
    others = [t for t in item.targets if t not in item.tests]
    if others:
        lines += ["", "Other members of the cluster (optional; note in test_ids_fixed any your fix also passes):",
                  "  " + " ".join(others[:12])]
    if prev_notes:
        lines += ["", "Notes from earlier workers on this cluster (their fixes were not merged):"]
        lines += [f"  * {n[:400]}" for n in prev_notes[-2:]]
    if rebase_patch and conflicted_files is not None:
        lines += ["", "REBASE: an earlier worker fixed this cluster, but its diff conflicted with newer main.",
                  f"It has been re-applied to your worktree with `git apply --3way` (original diff: {rebase_patch}).",
                  ("Files with conflict markers (<<<<<<< ours / ======= / >>>>>>> theirs): " + ", ".join(conflicted_files))
                  if conflicted_files else "It applied without conflicts this time; just verify it.",
                  "Resolve each conflict keeping the intent of BOTH sides (main's newer code and the earlier fix),",
                  "remove every marker line, then verify as usual. The gate rejects any leftover marker."]
    elif rebase_patch:
        lines += ["", "REBASE: an earlier worker fixed this cluster, but its diff no longer applies because main moved on.",
                  f"Its diff is at {rebase_patch}. Read it, re-apply the same change by hand to the current code",
                  "(the surrounding code may have changed), then verify as usual. Start from that diff, not from scratch."]
    if feature:
        lines += ["", w["feature_mode"].replace("{scratch}", str(scratch))]
    lines += ["", w["task_footer"], f"Finish by writing the result JSON to {out}."]
    return "\n".join(lines)


def launch(ctx: Ctx, a: argparse.Namespace, item: workqueue.WorkItem, seq: int) -> dict:
    w = ctx.worker
    tid = f"{ctx.id_prefix}w{seq:05d}"
    base = head(ctx)
    wt = ctx.worktree(tid)
    add_worktree(ctx, wt, base)
    out = ctx.results_dir / f"{tid}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    tdir = ctx.task_dir(tid)
    led = ledger(ctx)
    epoch = attempt_epoch(ctx)
    fails = [r for r in workqueue.counted_failures(led, epoch) if r.get("signature") == item.signature]
    prev = [r["result"]["notes"] for r in fails if (r.get("result") or {}).get("notes")]
    used = {r.get("rebase_of") for r in led.values()}
    conflicted = [r for r in led.values() if r.get("signature") == item.signature and is_conflict(r)
                  and r["id"] not in used and (ctx.task_dir(r["id"]) / "patch.diff").exists()]
    rebase_of = conflicted[-1]["id"] if conflicted else None
    rebase_patch = str(ctx.task_dir(rebase_of) / "patch.diff") if rebase_of else None
    conflicted_files = premerge_rebase(wt, rebase_patch, ctx.paths["code"]) if rebase_patch else None
    # A rebase of a feature worker's diff is feature-sized too: the small budget cannot re-apply it
    # (diagnosed 2026-10-12: 28 of the first 29 feature rejections were conflicts that then died as small rebases).
    feature = len(prev) >= ctx.cfg["queue"]["feature_after"] or bool(rebase_of and (led.get(rebase_of) or {}).get("feature"))
    # Effort ladder (agent-routing: one effort step up on the same model before any tier jump): the first
    # attempt runs at the configured effort; any attempt after a real failure (a lost merge race is not
    # one) and all feature work runs at high.
    effort = "high" if (feature or fails) else (a.effort or w["effort"] or None)
    timeout = max(a.timeout, w["feature_timeout"]) if feature else a.timeout
    scratch = ctx.scratch(tid)
    prompt = task_prompt(ctx, tid, item, out, prev, feature, rebase_patch, conflicted_files)
    if a.fake_mode:
        prompt += f"\n[fake:{a.fake_mode}]"
    sp = resolve(ctx.root, w["system_prompt"]) if w["system_prompt"] else None
    task = {"id": tid, "prompt": prompt, "out": str(out), "model": a.model, "tools": w["tools"],
            "allow": [f"Edit(/{wt}/**)", f"Edit(/{scratch}/**)", *w["allow"]],
            "system_prompt": sp.read_text() if sp else "", "timeout": timeout,
            "fake": {"code": ctx.paths["code"][0], "forbidden": (ctx.paths["forbidden"] or ["tests/"])[0],
                     "allowed": (ctx.paths["allowed"] or ["docs/NOTES.md"])[0]}}
    (tdir / "task.jsonl").write_text(json.dumps(task) + "\n")
    work = tdir / "fanout"
    if a.fake:
        cmd = [sys.executable, str(FAKE_WORKER), str(tdir / "task.jsonl"), "--work", str(work), "--cwd", str(wt)]
    else:
        schema = resolve(ctx.root, w["schema"]) if w["schema"] else SCHEMA
        cmd = [sys.executable, str(find_fanout()), "run", str(tdir / "task.jsonl"), "--work", str(work),
               "--schema", str(schema), "--cwd", str(wt), "--model", a.model, "--concurrency", "1",
               "--retries", "0", "--timeout", str(timeout)]
        if a.per_task_usd:
            cmd += ["--max-usd-per-task", str(max(a.per_task_usd, w["feature_usd"]) if feature else a.per_task_usd)]
        if effort:
            cmd += ["--effort", effort]
    with open(tdir / "runner.log", "w") as logf:
        p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True)
    rec = {"id": tid, "key": item.key, "signature": item.signature, "tests": item.tests,
           "targets": item.targets, "base": base, "status": "launched", "pid": p.pid,
           "cost_usd": 0.0, "result": None, "merged_commit": None, "reason": "",
           "t_launch": time.time(), "model": "fake" if a.fake else a.model, "feature": feature,
           "rebase_of": rebase_of, "effort": effort}
    ledger_put(ctx, rec)
    log(f"LAUNCH {tid} [{item.priority}] {'FEATURE ' if feature else ''}{'REBASE ' if rebase_of else ''}"
        f"{'HIGH ' if effort == 'high' else ''}{item.key}  tests: {', '.join(item.tests)}")
    return {"rec": rec, "proc": p}


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:   # a zombie or a recycled pid that is not ours
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
        return b"fanout" in cmd or b"fake_worker" in cmd
    except OSError:
        return False


def reap(ctx: Ctx, rec: dict) -> dict:
    """Process finished: fold the runner ledger + out JSON into the record, delete per-worker scratch."""
    tdir = ctx.task_dir(rec["id"])
    rows = read_jsonl(tdir / "fanout" / "ledger.jsonl")
    out = read_json(ctx.results_dir / f"{rec['id']}.json")
    rec.update(cost_usd=round(sum(r.get("cost") or 0 for r in rows), 4), t_done=time.time(),
               turns=sum(r.get("turns") or 0 for r in rows), denials=sum(r.get("denials") or 0 for r in rows),
               result=out if isinstance(out, dict) else None)
    if not rec["result"]:
        why = rows[-1].get("reason") if rows else "runner produced no ledger"
        rec.update(status="failed", reason=f"no result: {why}")
    elif rec["result"].get("status") != "fixed":
        rec.update(status="failed", reason=f"worker reported {rec['result'].get('status')}")
    else:
        rec.update(status="finished")
    ledger_put(ctx, rec)
    log(f"DONE   {rec['id']} {rec['status']} ${rec['cost_usd']:.3f} {rec.get('reason', '')}")
    # Scratch is never needed after the worker exits (diagnosed 2026-10-12: ~680 workers' /tmp/<id>/,
    # up to 170 MB each, filled the disk and the loop died on `git worktree add`).
    shutil.rmtree(ctx.scratch(rec["id"]), ignore_errors=True)
    if rec["status"] == "failed":
        remove_worktree(ctx, ctx.worktree(rec["id"]))
    return rec


def queue_input(ctx: Ctx, globs: str) -> dict:
    """known.json minus quarantined tests, restricted to this node's --only partition."""
    return only({t: r for t, r in tr.known(ctx).items() if not quarantined(ctx, t)}, globs)


def only(results: dict, globs: str) -> dict:
    """Restrict queue input to test ids matching any comma-separated glob."""
    if not globs:
        return results
    import fnmatch
    pats = globs.split(",")
    return {t: r for t, r in results.items() if any(fnmatch.fnmatchcase(t, p) for p in pats)}


def spent(ctx: Ctx) -> float:
    return sum(r.get("cost_usd") or 0 for r in ledger(ctx).values())


# ---------------------------------------------------------------- loop

def preflight(ctx: Ctx, a: argparse.Namespace) -> list[str]:
    """Problems that would waste a long run; empty when good to go."""
    errs = []
    if not a.fake and not shutil.which("claude"):
        errs.append("`claude` not on PATH")
    if not a.fake and not find_fanout().exists():
        errs.append(f"runner missing: {find_fanout()} (set $SWARM_FANOUT or install dispatching-subagents)")
    if not a.fake and not ctx.worker["system_prompt"]:
        errs.append("worker.system_prompt is not set")
    elif ctx.worker["system_prompt"] and not resolve(ctx.root, ctx.worker["system_prompt"]).exists():
        errs.append(f"worker.system_prompt missing: {ctx.worker['system_prompt']}")
    for rel in ctx.worker["preflight_files"]:
        if not (ctx.root / rel).exists():
            errs.append(f"missing {rel}")
    bad = merge.compat_available(ctx)
    if bad:
        errs.append(bad)
    try:
        head(ctx)
    except Exception as e:
        errs.append(f"no branch/commit in {ctx.root}: {e}")
    watched = tuple(ctx.paths["code"]) + (ctx.tests["tests_tree"],)
    dirty = [x for x in git(ctx.root, "status", "--porcelain", check=False).splitlines()
             if x and x[3:].startswith(watched)]
    if dirty:
        errs.append(f"main checkout has uncommitted changes under code/tests (fast-forward merges may fail): "
                    f"{', '.join(x[3:] for x in dirty[:5])}")
    junk = [f for f in git(ctx.root, "ls-files", check=False).splitlines()
            if any(j in f for j in ctx.paths["junk"])]
    if junk:
        errs.append(f"{len(junk)} build artefacts are tracked (e.g. {junk[0]}); `git rm -r --cached` them and "
                    "gitignore them, or every worker diff carries them")
    if getattr(a, "federate", False) and not a.only and not a.no_launch:
        errs.append("--federate without --only: the hub would chase every partition's root causes and "
                    "duplicate its siblings' work; give the hub its own partition")
    gb = free_gb(ctx.wt_root)
    if gb < ctx.cfg["run"]["min_free_gb"]:
        errs.append(f"only {gb:.1f} GB free on {ctx.wt_root} (run.min_free_gb {ctx.cfg['run']['min_free_gb']})")
    return errs


def exclude_state(ctx: Ctx) -> None:
    """Keep the state dirs out of `git status` without touching the project's .gitignore."""
    ex = Path(git(ctx.root, "rev-parse", "--git-path", "info/exclude").strip())
    ex = ex if ex.is_absolute() else ctx.root / ex
    lines = ex.read_text().splitlines() if ex.exists() else []
    want = []
    for key in ("state_dir", "rejected_dir"):
        p = resolve(ctx.root, ctx.cfg[key])
        try:
            want.append("/" + str(p.relative_to(ctx.root)).rstrip("/") + "/")
        except ValueError:
            pass
    new = [w for w in want if w not in lines]
    if new:
        ex.parent.mkdir(parents=True, exist_ok=True)
        ex.write_text("\n".join(lines + new) + "\n")


def take_lock(ctx: Ctx) -> str | None:
    """One loop per state dir. Two loops gating the same state corrupt known.json."""
    pf = ctx.state / "loop.pid"
    try:
        pid = int(pf.read_text().strip())
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
        if pid != os.getpid() and b"swarm" in cmd:
            return f"another loop is running (pid {pid}); `swarm.py stop` first"
    except (OSError, ValueError):
        pass
    pf.write_text(str(os.getpid()))
    return None


def reconcile(ctx: Ctx) -> None:
    """Records still `finished` whose commit already reached main (the loop died between the
    fast-forward and the ledger write) are marked merged instead of being gated twice."""
    led = ledger(ctx)
    open_ids = {r["id"] for r in led.values() if r["status"] in ("finished", "launched")}
    if not open_ids:
        return
    base = (read_json(ctx.state / "baseline.json", {}) or {}).get("commit")
    rng = f"{base}..HEAD" if base and git(ctx.root, "cat-file", "-t", base, check=False).strip() == "commit" else "HEAD"
    logtxt = git(ctx.root, "log", "--format=%H%x01%B%x00", rng, check=False)
    for chunk in logtxt.split("\x00"):
        sha, _, msg = chunk.strip().partition("\x01")
        m = re.search(r"(?m)^Swarm-Task:[ \t]*(\S+)", msg)
        if m and m.group(1) in open_ids and led[m.group(1)]["status"] == "finished":
            r = led[m.group(1)]
            r.update(status="merged", merged_commit=sha, reason="reconciled: found on main after a restart")
            ledger_put(ctx, r)
            log(f"reconciled {r['id']}: already on main as {sha[:10]}")


def run(ctx: Ctx, a: argparse.Namespace) -> int:
    errs = preflight(ctx, a)
    for e in errs:
        log(f"preflight: {e}")
    if errs and not a.force:
        log("fix these or pass --force")
        return 2
    lock = take_lock(ctx)
    if lock:
        log(lock)
        return 3
    exclude_state(ctx)
    event(ctx, f"loop start: {' '.join(sys.argv[1:])[:160]}", "loop")
    try:
        return _loop(ctx, a)
    finally:
        (ctx.state / "loop.pid").unlink(missing_ok=True)


def _loop(ctx: Ctx, a: argparse.Namespace) -> int:
    t_start = time.time()
    rcfg = ctx.cfg["run"]
    merge.refreshing(ctx, False)              # a marker left by a loop killed mid-refresh
    max_load = a.max_load or rcfg["max_load"] or 3.0 * (os.cpu_count() or 4)
    refresher: threading.Thread | None = None
    if a.sibling or a.federate:
        fed.ensure_remote(ctx, a.fed_remote)
    if a.sibling:
        # Seed the baseline from the hub, rebase onto its main, then re-baseline this node's
        # suites in the background (the seeded entries were measured on the hub, maybe hours ago).
        fed.sibling_fetch(ctx)
        fed.seed(ctx)
        fed.sibling_rebase(ctx)
        fst = fed.fstate(ctx)
        if fst.get("initial_refresh") != a.suites:
            fst["initial_refresh"] = a.suites
            fed.fstate_put(ctx, fst)
            refresher = threading.Thread(target=merge.refresh, args=(ctx,), kwargs={"do_bisect": False}, daemon=True)
            refresher.start()
    if refresher is None and (not (ctx.state / "baseline.json").exists() or not tr.known(ctx)):
        merge.refresh(ctx, do_bisect=False)
    reconcile(ctx)
    last_poll = last_pub = 0.0
    last_rebase = time.time() if a.sibling else 0.0
    pub_head = ""
    stop_launch = bool(a.no_launch)
    procs: dict[str, subprocess.Popen | None] = {}
    for r in ledger(ctx).values():            # adopt survivors of an interrupted run
        if r["status"] == "launched":
            procs[r["id"]] = None
    launched = 0
    idle_since = None
    # Worktrees of workers that ended in an earlier run are never needed again (their patch is
    # cached in the task dir). Diagnosed 2026-10-12: 40 of them held 5.6 GB.
    led0 = ledger(ctx)
    stale = [d for d in (ctx.wt_root.iterdir() if ctx.wt_root.exists() else [])
             if d.is_dir() and (led0.get(d.name) or {}).get("status") in ("merged", "rejected", "failed", "reverted")]
    for d in stale:
        remove_worktree(ctx, d)
        shutil.rmtree(ctx.scratch(d.name), ignore_errors=True)
    if stale:
        log(f"removed {len(stale)} worktrees of workers that ended in earlier runs")
    tree_checked = 0.0
    disk_warned = throttle_warned = 0.0
    while True:
        busy = refresher is not None and refresher.is_alive()
        if a.federate and not busy and time.time() - last_poll >= a.fed_poll:
            last_poll = time.time()
            try:
                fed.poll_candidates(ctx)
            except Exception as e:
                log(f"fed    poll error: {e}")
        if a.sibling and not busy and time.time() - last_rebase >= a.rebase_every:
            last_rebase = time.time()
            try:
                if fed.sibling_fetch(ctx):
                    fed.sibling_rebase(ctx)
            except Exception as e:
                log(f"fed    rebase error: {e}")
        led = ledger(ctx)
        for tid in list(procs):
            p = procs[tid]
            rec = led[tid]
            running = p.poll() is None if p else alive(rec.get("pid", -1))
            limit = max(a.timeout, ctx.worker["feature_timeout"]) if rec.get("feature") else a.timeout
            if running and time.time() - rec["t_launch"] > limit + 300:
                log(f"KILL   {tid}: over time")
                try:
                    os.killpg(rec["pid"], signal.SIGKILL)
                    if p:
                        p.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                running = False
            if not running:
                reap(ctx, rec)
                del procs[tid]
        finished = [r for r in ledger(ctx).values() if r["status"] == "finished"]
        refreshing = refresher is not None and refresher.is_alive()
        if not refreshing and time.time() - tree_checked > 120:
            # A suite builder committed to the tests tree on main: baseline only what changed,
            # now, not after the next full_every merges.
            tree_checked = time.time()
            changed = tr.changed_suites(ctx)
            if changed is None:
                log("tests tree changed outside the suite dirs; background full refresh")
                refresher = threading.Thread(target=merge.refresh, args=(ctx,), daemon=True)
            elif changed:
                log(f"tests tree changed: suites {', '.join(changed)}; background suite refresh")
                refresher = threading.Thread(target=merge.refresh_suites, args=(ctx, changed), daemon=True)
            if changed is None or changed:
                refresher.start()
                refreshing = True
        if not refreshing:                    # the gate tree and known.json belong to refresh
            for i in range(0, len(finished), ctx.batch):
                batch = finished[i:i + ctx.batch]
                merge.merge_batch(ctx, batch)
                for r in batch:
                    remove_worktree(ctx, ctx.worktree(r["id"]))
            if (read_json(ctx.state / "counters.json", {}) or {}).get("merges_since_full", 0) >= ctx.full_every:
                refresher = threading.Thread(target=merge.refresh, args=(ctx,), daemon=True)
                refresher.start()
                refreshing = True
        if (a.federate or a.sibling) and (time.time() - last_pub >= 60 or head(ctx) != pub_head):
            last_pub, pub_head = time.time(), head(ctx)
            try:
                fed.hub_publish(ctx) if a.federate else fed.publish_cand(ctx, a.sibling)
            except Exception as e:
                log(f"fed    publish error: {e}")
        if a.max_usd and spent(ctx) >= a.max_usd and not stop_launch:
            log(f"spend ${spent(ctx):.2f} reached --max-usd; no more launches")
            stop_launch = True
        if a.max_workers and launched >= a.max_workers:
            stop_launch = True
        if a.max_minutes and time.time() - t_start > a.max_minutes * 60:
            log(f"--max-minutes {a.max_minutes} reached: exiting; {len(procs)} workers keep running "
                "and are adopted when the loop is relaunched")
            event(ctx, "loop exit at --max-minutes (relaunch to continue)", "loop")
            break
        overloaded = os.getloadavg()[0] > max_load
        gb = free_gb(ctx.wt_root)
        low_disk = gb < rcfg["min_free_gb"]
        if low_disk and time.time() - disk_warned > 600:
            disk_warned = time.time()
            log(f"DISK   only {gb:.1f} GB free on {ctx.wt_root}: no launches until it recovers")
        if overloaded and not stop_launch and len(procs) < a.concurrency and time.time() - throttle_warned > 600:
            throttle_warned = time.time()
            log(f"THROTTLE load {os.getloadavg()[0]:.1f} > {max_load:.0f} with {a.concurrency - len(procs)} free "
                "slots: CPU-bound; if this persists, scale out to sibling containers (references/scaling-out.md)")
        if not stop_launch and not overloaded and not low_disk and len(procs) < a.concurrency:
            items = workqueue.build(ctx.cfg["queue"], queue_input(ctx, a.only), ledger(ctx), source_size(ctx),
                                    epoch=attempt_epoch(ctx))
            if not items and not procs and not finished and not refreshing:
                # Idle: wait for a suite builder to commit new tests (the 120 s tree check picks
                # them up), else exit after idle_max.
                idle_since = idle_since or time.time()
                if time.time() - idle_since > a.idle_max:
                    log("queue empty and nothing in flight")
                    event(ctx, "partition exhausted: loop exit", "loop")
                    break
                if time.time() - throttle_warned > 600:
                    throttle_warned = time.time()
                    log("IDLE   no dispatchable work on this node (partition exhausted, or all parked): "
                        "add test supply, re-partition, or stand this node down")
                time.sleep(min(30, max(a.poll, a.idle_max / 10)))
                continue
            idle_since = None
            seq = len(ledger(ctx)) + 1
            led = ledger(ctx)
            fails = Counter(r.get("signature") for r in workqueue.counted_failures(led, attempt_epoch(ctx))
                            if (r.get("result") or {}).get("notes"))
            flying = {r.get("signature") for r in led.values() if r.get("status") == "launched"}
            fa = ctx.cfg["queue"]["feature_after"]
            for item in items:
                if len(procs) >= a.concurrency or (a.max_workers and launched >= a.max_workers):
                    break
                if fails[item.signature] >= fa:
                    if item.signature in flying:
                        continue          # one feature worker per signature: shards would collide
                    flying.add(item.signature)
                w = launch(ctx, a, item, seq)
                procs[w["rec"]["id"]] = w["proc"]
                seq += 1
                launched += 1
        if stop_launch and not procs and not refreshing and (not a.federate or a.no_launch) and \
                not any(r["status"] == "finished" for r in ledger(ctx).values()):
            break
        time.sleep(a.poll)
    if refresher is not None and refresher.is_alive():
        log("waiting for the background refresh to finish")
        refresher.join()
    if a.final_refresh:
        merge.refresh(ctx)
    status(ctx)
    return 0


# ---------------------------------------------------------------- status / control

def signals(ctx: Ctx, led: dict, items: list, max_load: float) -> list[str]:
    """Check-in signals: each names a condition from the runbook's failure modes and its fix."""
    out = []
    finished = sum(1 for r in led.values() if r["status"] == "finished")
    live = sum(1 for r in led.values() if r["status"] == "launched")
    rf = read_json(ctx.state / "refreshing.json")
    if rf:
        out.append(f"REFRESHING: {rf.get('what')} refresh running for {int((time.time() - rf['started']) / 60)} min; "
                   "merging is paused until it ends (a full refresh past ~1 h: raise gate.full_every)")
    if finished > 2 * max(ctx.batch, 1) and not rf:
        out.append(f"GATE BACKLOG: {finished} finished workers await the gate; raise --batch, lower --sample, "
                   "or lower --concurrency so the gate gets CPU")
    load = os.getloadavg()[0]
    if load > max_load and items:
        out.append(f"CPU-BOUND: load {load:.1f} > {max_load:.0f} with {len(items)} dispatchable items; "
                   "scale out to sibling containers (references/scaling-out.md)")
    if not items and not live:
        out.append("PARTITION EXHAUSTED: nothing dispatchable and nothing in flight; add test supply, "
                   "re-partition, `unpark` after a harness fix, or stand this node down")
    elif len(items) < 10 and live:
        out.append(f"SUPPLY LOW: {len(items)} dispatchable items left; start a suite builder now")
    if free_gb(ctx.wt_root) < 2 * ctx.cfg["run"]["min_free_gb"]:
        out.append(f"DISK LOW: {free_gb(ctx.wt_root):.1f} GB free; check /tmp scratch and {ctx.wt_root}")
    recent = sorted((r for r in led.values() if r.get("t_done")), key=lambda r: r["t_done"])[-20:]
    if len(recent) >= 10:
        why = Counter(str(r.get("reason", "")).split(":")[0] for r in recent if r["status"] == "failed")
        top = why.most_common(1)
        if top and top[0][1] >= 0.6 * len(recent):
            out.append(f"SAME FAILURE: {top[0][1]}/{len(recent)} recent workers failed with '{top[0][0]}'; "
                       "a prompt/auth/permission bug, not bad luck: stop and fix")
        if sum(r.get("denials") or 0 for r in recent) >= 5:
            out.append("DENIALS: recent workers hit permission denials; check worker.allow against the prompt")
    gated = sorted((r for r in led.values() if r.get("t_gate")), key=lambda r: r["t_gate"])[-15:]
    if len(gated) >= 10 and not any(r["status"] == "merged" for r in gated):
        reasons = Counter(str(r.get("reason", ""))[:60] for r in gated)
        out.append(f"GATE REJECTS ALL: last {len(gated)} gated candidates rejected (top: {reasons.most_common(1)[0][0]}); "
                   "one test 'regressing' in all of them = stale known state or a cross-partition regression: "
                   "re-baseline that suite")
    k = tr.known(ctx)
    base = read_json(ctx.state / "baseline.json", {}) or {}
    if base.get("suite_names") is not None:
        new = [s for s in tr.list_suites(ctx, ctx.root) if s not in base["suite_names"]]
        if new:
            out.append(f"UNBASELINED SUITES: {', '.join(new[:6])} (the loop baselines them within 2 min; "
                       "else `refresh --only-suites`)")
    stages = Counter(r.get("stage") for r in k.values() if not tr.is_pass(r) and r.get("status") != "SKIP")
    total = sum(stages.values())
    if total >= 50 and stages.most_common(1)[0][1] > 0.9 * total:
        out.append(f"ONE STAGE: {stages.most_common(1)[0][1]}/{total} failures carry stage "
                   f"'{stages.most_common(1)[0][0]}'; the runner's stage labelling is probably broken (`doctor`)")
    return out


def conflict_hot_spots(led: dict) -> list[tuple[str, int]]:
    """Files named in conflict rejections: a shared registry here wants self-registering modules."""
    c: Counter = Counter()
    for r in led.values():
        if is_conflict(r):
            for f in set(re.findall(r"(?<![\w/])([\w.+-]+(?:/[\w.+-]+)+\.\w+)", str(r.get("reason", "")))):
                c[f] += 1
    return c.most_common(5)


def status(ctx: Ctx) -> int:
    led = ledger(ctx)
    by = Counter(r["status"] for r in led.values())
    cost = spent(ctx)
    merged = by.get("merged", 0)
    pf = ctx.state / "loop.pid"
    pid = pf.read_text().strip() if pf.exists() else ""
    loop = f"loop pid {pid} {'alive' if pid and Path(f'/proc/{pid}').exists() else 'DEAD (stale pid file)'}" if pid \
        else "loop not running"
    max_load = ctx.cfg["run"]["max_load"] or 3.0 * (os.cpu_count() or 4)
    print(f"{loop}  load {os.getloadavg()[0]:.1f} (throttle {max_load:.0f})  disk {free_gb(ctx.wt_root):.1f} GB free")
    print(f"workers: {len(led)} total  " + "  ".join(f"{k} {v}" for k, v in sorted(by.items())))
    print(f"spend: ${cost:.3f}" + (f"  (${cost / merged:.3f} per merge)" if merged else ""))
    feats = sum(1 for r in led.values() if r.get("feature"))
    rebases = sum(1 for r in led.values() if r.get("rebase_of"))
    conflicts = sum(1 for r in led.values() if is_conflict(r))
    denials = sum(r.get("denials") or 0 for r in led.values())
    print(f"feature workers {feats}  rebase workers {rebases}  lost merge races {conflicts}  permission denials {denials}")
    print(f"finished awaiting gate: {by.get('finished', 0)}")
    merges = [r for r in led.values() if r["status"] == "merged" and r.get("t_gate")]
    if merges:
        last = max(r["t_gate"] for r in merges)
        hour = sum(1 for r in merges if r["t_gate"] > time.time() - 3600)
        print(f"last merge {int(time.time() - last)}s ago; {hour} merges in the last hour")
    c = read_json(ctx.state / "counters.json", {}) or {}
    print(f"merges since last full run: {c.get('merges_since_full', 0)}")
    hist = read_jsonl(ctx.state / "history.jsonl")
    if hist:
        suites = sorted({s for h in hist for s in h["suites"]})
        print("pass counts over time:")
        print("  " + f"{'time':<9}{'commit':<11}{'merges':>7} " + " ".join(f"{s[:14]:>15}" for s in suites))
        for h in hist[-8:]:
            cells = [f"{h['suites'][s]['pass']}/{h['suites'][s]['total']}" if s in h["suites"] else "-"
                     for s in suites]
            print("  " + f"{time.strftime('%H:%M', time.localtime(h['time'])):<9}{h['commit'][:10]:<11}"
                  f"{h.get('merges_total', 0):>7} " + " ".join(f"{x:>15}" for x in cells))
    k = tr.known(ctx)
    items: list = []
    if k:
        counts = tr.suite_counts(k)
        print("known now: " + ", ".join(f"{s} {v['pass']}/{v['total']}" for s, v in sorted(counts.items())))
        items = workqueue.build(ctx.cfg["queue"], {t: r for t, r in k.items() if not quarantined(ctx, t)}, led,
                                epoch=attempt_epoch(ctx))
        failing = sum(1 for t, r in k.items() if not tr.is_pass(r) and r.get("status") != "SKIP")
        print(f"queue: {len(items)} dispatchable items; {failing} failing tests known "
              "(this view ignores the node's --only; `queue --only` for the partition)")
    rej = Counter(r["reason"].split(":")[0] for r in led.values() if r["status"] in ("rejected", "failed"))
    if rej:
        print("top rejection/failure reasons: " + "; ".join(f"{n}x {w}" for w, n in rej.most_common(6)))
    hot = conflict_hot_spots(led)
    if hot:
        print("conflict hot spots: " + ", ".join(f"{f} ({n})" for f, n in hot))
    live = [r for r in led.values() if r["status"] == "launched"]
    for r in live[:10]:
        print(f"  in flight {r['id']} {int(time.time() - r['t_launch'])}s {r['key'][:80]}")
    sig = signals(ctx, led, items, max_load)
    print("SIGNALS: " + ("none" if not sig else ""))
    for x in sig:
        print(f"  ! {x}")
    return 0


def stop(ctx: Ctx, workers: bool) -> int:
    """Stop the loop and the test processes it started (they survive a plain kill: ppid 1,
    still burning CPU). With workers=True, kill in-flight workers too (else they are adopted
    on the next launch)."""
    pf = ctx.state / "loop.pid"
    if pf.exists():
        try:
            pid = int(pf.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            log(f"sent SIGTERM to loop {pid}")
            time.sleep(2)
        except (OSError, ValueError) as e:
            log(f"loop pid file stale: {e}")
        pf.unlink(missing_ok=True)
    killed = 0
    gate = os.path.realpath(ctx.gate_tree)
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == os.getpid():
            continue
        try:
            cwd = os.readlink(d / "cwd")
        except OSError:
            continue
        if cwd == gate or cwd.startswith(gate + "/"):
            try:
                os.kill(int(d.name), signal.SIGKILL)
                killed += 1
            except OSError:
                pass
    log(f"killed {killed} processes running in the gate tree")
    event(ctx, "loop stopped", "loop")
    if workers:
        n = 0
        for r in ledger(ctx).values():
            if r["status"] == "launched" and alive(r.get("pid", -1)):
                try:
                    os.killpg(r["pid"], signal.SIGKILL)
                    n += 1
                except OSError:
                    pass
        log(f"killed {n} in-flight workers (they are reaped as failed on the next launch)")
    return 0


def unpark(ctx: Ctx) -> int:
    """After a harness fix: attempts before now no longer count toward parking or feature mode."""
    write_json(ctx.state / "epoch.json", {"epoch": time.time(), "set": time.strftime("%Y-%m-%dT%H:%M:%S")})
    event(ctx, "attempt epoch: parked tests unparked", "unpark")
    items = workqueue.build(ctx.cfg["queue"], tr.known(ctx), ledger(ctx), epoch=attempt_epoch(ctx))
    log(f"attempt epoch set to now; {len(items)} dispatchable items")
    return 0
