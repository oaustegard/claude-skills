"""Model arms on the swarm's failing tail: same clusters, prompt, budget and base commit.

    swarm.py compare select --out SET.json [--n 60] [--min-fails 1] [--ledger L.jsonl ...] [--root DIR]
    swarm.py compare run    --set SET.json --work DIR [--n 20] [--reps 2] [--concurrency 6] [--arms a,b]
    swarm.py compare report --work DIR

`select` takes the ABANDONED TAIL: failing clusters the swarm already attempted
(>= --min-fails counted failures in the ledgers, or a parked test), most-failed
first, round-robin across suites, and pins HEAD as the base. Random failing
clusters saturate (both arms solve them; diagnosed 2026-10-12, run 1: 38/40).
`run` first BASE-CHECKS the set: a cluster whose representatives pass at the
base is dropped (known.json goes stale for suites this node does not run: only
4/18 and 10/33 still failed in runs 2 and 3). Each (cluster, arm, rep) is one
headless worker in its own worktree at the base; each patch is graded in
isolation: SOLVED = a representative flips to PASS and nothing in always_suites
plus a fixed passing sample regresses. Nothing is merged. Resumable.
Run this in its own container (a sibling session) so it does not steal the hub's CPU.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

from swarmkit import config as cfgmod
from swarmkit import testrun as tr
from swarmkit import workqueue
from swarmkit.common import SCHEMA, Ctx, find_fanout, read_jsonl
from swarmkit.config import resolve


def ctx_from(a) -> Ctx:
    root = (a.root or Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                                          text=True, check=False).stdout.strip() or ".")).resolve()
    cfg_path = a.config or root / "swarm.toml"
    return Ctx(root=root, cfg=cfgmod.load(cfg_path if cfg_path.exists() else None))


def sh(cwd: Path, *a: str, check: bool = True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(list(a), cwd=cwd, check=check, capture_output=True, text=True,
                          errors="surrogateescape", **kw)


def select(ctx: Ctx, a) -> int:
    known = tr.known(ctx)
    keep = frozenset(ctx.cfg["queue"]["keep_words"])
    clusters = workqueue.clusters(known, keep)
    recs: dict = {}
    for p in [ctx.state / "ledger.jsonl", *map(Path, a.ledger or [])]:
        for r in read_jsonl(p):
            recs[r["id"]] = r
    by_sig, by_test = collections.Counter(), collections.Counter()
    for r in workqueue.counted_failures(recs, 0):
        w = 1 if r.get("result") else 0.5
        by_sig[r.get("signature")] += w
        for t in r.get("tests", []):
            by_test[t] += w
    hard = []
    for sig, tids in clusters.items():
        fails = max(by_sig.get(sig, 0), max((by_test.get(t, 0) for t in tids), default=0))
        parked = any(by_test.get(t, 0) >= ctx.cfg["queue"]["max_test_attempts"] for t in tids)
        if fails >= a.min_fails or parked:
            hard.append((sig, sorted(tids, key=lambda t: (-by_test.get(t, 0), t)), fails))
    print(f"{len(hard)} of {len(clusters)} failing clusters were attempted >= {a.min_fails} times or are parked")
    by_suite = collections.defaultdict(list)
    for h in hard:
        by_suite[tr.suite_of(h[1][0])].append(h)
    rng = random.Random(20261012)
    for v in by_suite.values():
        rng.shuffle(v)
        v.sort(key=lambda c: c[2])
    picked = []
    while len(picked) < a.n and any(by_suite.values()):
        for s in sorted(by_suite):
            if by_suite[s] and len(picked) < a.n:
                picked.append(by_suite[s].pop())
    cheap = set(ctx.gate["cheap_suites"])
    passing = sorted(t for t, r in known.items() if tr.is_pass(r) and tr.suite_of(t) in cheap)
    sample = sorted(rng.sample(passing, min(ctx.cfg["compare"]["sample"], len(passing))))
    base = sh(ctx.root, "git", "rev-parse", "HEAD").stdout.strip()
    items = [{"key": f"c{i:02d}", "signature": sig, "tests": tids[:3], "members": tids[:20], "fails": fails,
              "reasons": {t: known[t].get("reason", "") for t in tids[:3]}} for i, (sig, tids, fails) in enumerate(picked)]
    Path(a.out).write_text(json.dumps({"base": base, "items": items, "sample": sample}, indent=1))
    print(f"{len(items)} clusters at {base[:10]} -> {a.out} (the run step base-checks them)")
    return 0


def prompt(ctx: Ctx, item: dict, wt: Path, out: Path, tid: str, scratch: Path) -> str:
    w = ctx.worker
    lines = [f"Task id: {tid}", f"Your worktree (current directory): {wt}", f"Result JSON out path: {out}",
             f"Scratch dir: {scratch}/", "", f"Failure cluster: {item['signature']}", "", "Representative tests to fix:"]
    for t in item["tests"]:
        lines += [f"  - {t}", f"    reason: {item['reasons'].get(t, '')}"]
        if w["repro_command"]:
            lines.append("    run: " + w["repro_command"].format(suite=tr.suite_of(t), test=t))
    others = [t for t in item["members"] if t not in item["tests"]]
    if others:
        lines += ["", "Other members of the cluster (optional):", "  " + " ".join(others[:12])]
    lines += ["", w["task_footer"], f"Finish by writing the result JSON to {out}."]
    return "\n".join(lines)


def one(ctx: Ctx, job, base: str, sample: list[str], work: Path) -> dict:
    item, arm, rep = job
    spec = ctx.cfg["compare"]["arms"][arm]
    tid = f"cmp-{item['key']}-{arm}-{rep}"
    wt, out, tdir = work / "wt" / tid, work / "out" / f"{tid}.json", work / "tasks" / tid
    scratch = Path(ctx.worker["scratch"].format(id=tid))
    if wt.exists():
        sh(ctx.root, "git", "worktree", "remove", "--force", str(wt), check=False)
    sh(ctx.root, "git", "worktree", "add", "--detach", "--force", str(wt), base)
    from swarmkit.common import link_untracked
    link_untracked(ctx, wt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    tdir.mkdir(parents=True, exist_ok=True)
    w = ctx.worker
    task = {"id": tid, "prompt": prompt(ctx, item, wt, out, tid, scratch), "out": str(out), "model": spec["model"],
            "tools": w["tools"], "allow": [f"Edit(/{wt}/**)", f"Edit(/{scratch}/**)", *w["allow"]],
            "system_prompt": resolve(ctx.root, w["system_prompt"]).read_text(), "timeout": w["timeout"]}
    (tdir / "task.jsonl").write_text(json.dumps(task) + "\n")
    cmd = [sys.executable, str(find_fanout()), "run", str(tdir / "task.jsonl"), "--work", str(tdir / "fanout"),
           "--schema", str(resolve(ctx.root, w["schema"]) if w["schema"] else SCHEMA), "--cwd", str(wt),
           "--model", spec["model"], "--concurrency", "1", "--retries", "0", "--timeout", str(w["timeout"]),
           "--max-usd-per-task", str(ctx.cfg["compare"]["usd_cap"])]
    if spec.get("effort"):
        cmd += ["--effort", spec["effort"]]
    t0 = time.time()
    subprocess.run(cmd, capture_output=True, text=True, check=False)
    secs = time.time() - t0
    rows = read_jsonl(tdir / "fanout" / "ledger.jsonl")
    led = rows[-1] if rows else {}
    result = json.loads(out.read_text()) if out.exists() else None
    sh(wt, "git", "add", "-A", check=False)
    patch = sh(wt, "git", "diff", "--cached", "--no-renames", "--binary", base, "--", *ctx.paths["code"],
               check=False).stdout
    shutil.rmtree(scratch, ignore_errors=True)
    rec = {"key": item["key"], "arm": arm, "rep": rep, "signature": item["signature"], "secs": round(secs),
           "cost": led.get("cost"), "turns": led.get("turns"), "reported": (result or {}).get("status"),
           "patch_lines": patch.count("\n")}
    sh(wt, "git", "reset", "-q", "--hard", base, check=False)       # grade base + the code patch only
    sh(wt, "git", "clean", "-fdq", check=False)
    applied = bool(patch.strip()) and sh(wt, "git", "apply", "--binary", "-", check=False, input=patch).returncode == 0
    if applied:
        always = [t for t, r in tr.known(ctx).items() if tr.suite_of(t) in set(ctx.gate["always_suites"]) and tr.is_pass(r)]
        res = tr.run_ids(ctx, wt, item["members"] + sample + always, jobs=2)
        flipped = [t for t in item["members"] if tr.is_pass(res.get(t))]
        regress = [t for t in sample + always if res.get(t, {}).get("status") not in ("PASS", "MISSING")]
        rec.update(flipped=len(flipped), reps_flipped=sum(t in flipped for t in item["tests"]),
                   regressions=regress[:10], n_regressions=len(regress))
    else:
        rec.update(flipped=0, reps_flipped=0, regressions=[], n_regressions=0)
    rec["solved"] = rec["reps_flipped"] > 0 and rec["n_regressions"] == 0
    (work / "patches").mkdir(exist_ok=True)
    (work / "patches" / f"{tid}.diff").write_text(patch, errors="surrogateescape")
    sh(ctx.root, "git", "worktree", "remove", "--force", str(wt), check=False)
    return rec


def run(ctx: Ctx, a) -> int:
    spec = json.loads(Path(a.set).read_text())
    work = Path(a.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    done_path = work / "results.jsonl"
    done = {(r["key"], r["arm"], r["rep"]) for r in read_jsonl(done_path)}
    bpath = work / "base.json"
    if not bpath.exists():          # base check: the selection's known.json can be stale
        bt = work / "wt" / "_base"
        sh(ctx.root, "git", "worktree", "add", "--detach", "--force", str(bt), spec["base"], check=False)
        from swarmkit.common import link_untracked
        link_untracked(ctx, bt)
        ids = [t for i in spec["items"] for t in i["members"]] + spec["sample"]
        bpath.write_text(json.dumps(tr.run_ids(ctx, bt, ids, jobs=2)))
        sh(ctx.root, "git", "worktree", "remove", "--force", str(bt), check=False)
    bres = json.loads(bpath.read_text())
    still = [i for i in spec["items"] if not any(tr.is_pass(bres.get(t)) for t in i["tests"])]
    items = still[:a.n]
    sample = [t for t in spec["sample"] if tr.is_pass(bres.get(t))]
    for i in items:
        i["members"] = [t for t in i["members"] if not tr.is_pass(bres.get(t))]
    print(f"base check: {len(still)}/{len(spec['items'])} clusters still fail at {spec['base'][:10]} "
          f"(running {len(items)}), {len(sample)} sample tests pass", flush=True)
    arms = a.arms.split(",") if a.arms else list(ctx.cfg["compare"]["arms"])
    jobs = [(i, arm, rep) for i in items for rep in range(a.reps) for arm in arms if (i["key"], arm, rep) not in done]
    print(f"{len(jobs)} jobs to run, {len(done)} done", flush=True)
    with cf.ThreadPoolExecutor(a.concurrency) as ex:
        futs = {ex.submit(one, ctx, j, spec["base"], sample, work): j for j in jobs}
        for f in cf.as_completed(futs):
            try:
                rec = f.result()
            except Exception as e:
                print("job failed:", futs[f][0]["key"], futs[f][1], futs[f][2], repr(e)[:200], flush=True)
                continue
            with done_path.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(f"{rec['key']} {rec['arm']}#{rec['rep']}: solved={rec['solved']} flipped={rec['flipped']} "
                  f"regr={rec['n_regressions']} ${rec['cost'] or 0:.3f} {rec['secs']}s", flush=True)
    return 0


def report(a) -> int:
    rows = read_jsonl(Path(a.work) / "results.jsonl")
    if not rows:
        print("no results yet")
        return 1
    by = collections.defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0
    print("| arm | runs | solved | solve rate | clusters solved (any rep) | $ total | $ per solve | median turns | median s |")
    print("|---|---|---|---|---|---|---|---|---|")
    for arm, rs in by.items():
        solved = sum(r["solved"] for r in rs)
        cost = sum(r["cost"] or 0 for r in rs)
        print(f"| {arm} | {len(rs)} | {solved} | {solved / len(rs):.0%} | {len({r['key'] for r in rs if r['solved']})} | "
              f"{cost:.2f} | {cost / solved if solved else float('nan'):.3f} | {med([r['turns'] or 0 for r in rs])} | "
              f"{med([r['secs'] for r in rs])} |")
    keys = {r["key"] for r in rows}
    solved = {arm: {r["key"] for r in rs if r["solved"]} for arm, rs in by.items()}
    arms = list(by)
    for i, x in enumerate(arms):
        for y in arms[i + 1:]:
            print(f"clusters {len(keys)}; {x} vs {y}: both {len(solved[x] & solved[y])}, only {x} "
                  f"{len(solved[x] - solved[y])}, only {y} {len(solved[y] - solved[x])}, "
                  f"neither {len(keys - solved[x] - solved[y])}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("select", "run", "report"):
        p = sp.add_parser(name)
        p.add_argument("--root", type=Path)
        p.add_argument("--config", type=Path)
        if name == "select":
            p.add_argument("--out", required=True)
            p.add_argument("--n", type=int, default=60, help="pool size; run keeps --n still failing")
            p.add_argument("--min-fails", type=float, default=1)
            p.add_argument("--ledger", nargs="*", help="extra ledgers (siblings') to count attempts from")
        elif name == "run":
            p.add_argument("--set", required=True)
            p.add_argument("--work", required=True)
            p.add_argument("--n", type=int, default=20)
            p.add_argument("--reps", type=int, default=2)
            p.add_argument("--concurrency", type=int, default=6)
            p.add_argument("--arms", default="", help="comma subset of compare.arms")
        else:
            p.add_argument("--work", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "report":
        return report(a)
    ctx = ctx_from(a)
    return select(ctx, a) if a.cmd == "select" else run(ctx, a)
