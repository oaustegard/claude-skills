#!/usr/bin/env python3
"""Swarm harness CLI: hundreds of headless workers fix clusters of failing tests behind a merge gate.

    swarm.py run      [--config swarm.toml] [--root DIR] [--concurrency 24] [--max-usd 50] ...
    swarm.py status   | queue [--top 20] | refresh [--only-suites a,b] | unpark | stop [--workers]
    swarm.py fed-publish | fed-poll | fed-status          # one-shot federation actions (hub)
    swarm.py fed-export-ledger NAME                       # sibling stand-down, after user approval
    swarm.py cluster  RESULTS.json [...] [--top 30]       # cluster any test-command JSON output
    swarm.py doctor   [RESULTS.json ...] [--run-suite S]  # check the runner's JSON before launch
    swarm.py event    "TEXT"                              # annotate a harness change for the stats
    swarm.py stats    [--out DIR] [--ledger L.jsonl ...]  # metrics.json, report.md, charts
    swarm.py compare  select|run|report ...               # model arms on the failing tail
    swarm.py selftest [--keep]                            # every gate path on a fake project

--root defaults to the git toplevel of the current directory; --config defaults
to <root>/swarm.toml. Flags override the config's [run]/[gate]/[worker] values.
See SKILL.md for the runbook and references/config.md for every config key.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from swarmkit import config as cfgmod
from swarmkit.common import Ctx, ledger

CMDS = ["run", "status", "queue", "refresh", "unpark", "stop", "fed-publish", "fed-poll", "fed-status",
        "fed-export-ledger",
        "cluster", "doctor", "event", "stats", "compare", "selftest"]


def toplevel() -> Path:
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    return Path(p.stdout.strip() or ".").resolve()


def parser(cfg: dict) -> argparse.ArgumentParser:
    r, g, w, f = cfg["run"], cfg["gate"], cfg["worker"], cfg["federation"]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=CMDS)
    ap.add_argument("rest", nargs="*", help="cluster: result files; compare: select|run|report")
    ap.add_argument("--config", type=Path)
    ap.add_argument("--root", type=Path)
    ap.add_argument("--wt-root", type=Path)
    ap.add_argument("--max-workers", type=int, default=0, help="launches in this invocation (0 = no cap)")
    ap.add_argument("--concurrency", type=int, default=r["concurrency"])
    ap.add_argument("--max-usd", type=float, default=0, help="stop launching at this total ledger spend")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="exit cleanly after this long (use 110 under a 2-hour background-job cap)")
    ap.add_argument("--per-task-usd", type=float, default=w["per_task_usd"])
    ap.add_argument("--model", default=w["model"])
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--timeout", type=int, default=w["timeout"], help="seconds per worker")
    ap.add_argument("--fake", action="store_true", help="fake_worker.py instead of claude (no model calls)")
    ap.add_argument("--fake-mode", default="", help="force a fake_worker mode on every task")
    ap.add_argument("--jobs", type=int, default=4, help="test parallelism in gate/baseline")
    ap.add_argument("--batch", type=int, default=g["batch"])
    ap.add_argument("--sample", type=int, default=g["sample"])
    ap.add_argument("--full-every", type=int, default=g["full_every"])
    ap.add_argument("--quick-every", type=int, default=g["quick_every"],
                    help="merges between quick refreshes of the quick suites (0 = off)")
    ap.add_argument("--quick-suites", default=",".join(g["quick_suites"]),
                    help="comma list (default gate.quick_suites, else gate.cheap_suites)")
    ap.add_argument("--idle-refresh", action=argparse.BooleanOptionalAction, default=g["idle_refresh"],
                    help="full refresh when the queue drains with merges since the last one (default on)")
    ap.add_argument("--final-refresh", action="store_true")
    ap.add_argument("--suites", default="", help="comma list: this node's suites (default every suite)")
    ap.add_argument("--only-suites", default="", help="refresh: baseline only these suites")
    ap.add_argument("--poll", type=float, default=r["poll"])
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--force", action="store_true", help="run despite preflight problems")
    ap.add_argument("--only", default="", help="comma globs on test ids: dispatch only these failures")
    ap.add_argument("--idle-max", type=float, default=r["idle_max"])
    ap.add_argument("--max-load", type=float, default=0, help="no launches above this 1-min load (0 = config)")
    ap.add_argument("--sibling", default="", metavar="NAME", help="federated sibling NAME")
    ap.add_argument("--federate", action="store_true", help="federated hub: ingest candidates, publish main+state")
    ap.add_argument("--fed-remote", default=f["remote"])
    ap.add_argument("--fed-poll", type=float, default=f["poll"])
    ap.add_argument("--rebase-every", type=float, default=f["rebase_every"])
    ap.add_argument("--no-launch", action="store_true", help="launch no workers (hub: ingest only)")
    ap.add_argument("--workers", action="store_true", help="stop: also kill in-flight workers")
    ap.add_argument("--run-suite", default="", help="doctor: run this suite through the test command")
    ap.add_argument("--out", type=Path, help="stats: output dir (default <state>/../stats)")
    ap.add_argument("--ledger", nargs="*", default=[], help="stats: extra (sibling) ledgers")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["selftest"]:
        from swarmkit import selftest
        return selftest.main(argv[1:])
    if argv[:1] == ["compare"]:
        from swarmkit import compare
        return compare.main(argv[1:])
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", type=Path)
    pre.add_argument("--root", type=Path)
    k, _ = pre.parse_known_args(argv)
    root = (k.root or toplevel()).resolve()
    cfg_path = k.config or (root / "swarm.toml")
    cfg = cfgmod.load(cfg_path if (k.config or cfg_path.exists()) else None)
    a = parser(cfg).parse_args(argv)
    ctx = Ctx(root=root, cfg=cfg, wt_root=a.wt_root, jobs=a.jobs, batch=a.batch, sample_size=a.sample,
              full_every=a.full_every, quick_every=a.quick_every, idle_refresh=a.idle_refresh,
              quick_suites=[s for s in a.quick_suites.split(",") if s], suites=[s for s in a.suites.split(",") if s],
              id_prefix=f"{a.sibling}-" if a.sibling else "", stamp_fixed=bool(a.sibling))
    from swarmkit import federation as fed
    from swarmkit import merge, run, workqueue
    from swarmkit import testrun as tr
    if a.cmd.startswith("fed-"):
        fed.ensure_remote(ctx, a.fed_remote)
        if a.cmd == "fed-publish":
            fed.hub_publish(ctx, force_state=True)
        elif a.cmd == "fed-poll":
            print(f"{fed.poll_candidates(ctx)} new candidates")
        elif a.cmd == "fed-export-ledger":
            return 0 if fed.export_ledger(ctx, (a.rest or [a.sibling or "node"])[0]) else 1
        fed.status(ctx)
        return 0
    if a.cmd == "status":
        return run.status(ctx)
    if a.cmd == "stop":
        return run.stop(ctx, a.workers)
    if a.cmd == "unpark":
        return run.unpark(ctx)
    if a.cmd == "refresh":
        if a.only_suites:
            merge.refresh_suites(ctx, [s for s in a.only_suites.split(",") if s])
        else:
            merge.refresh(ctx)
        return 0
    if a.cmd == "queue":
        from swarmkit.common import attempt_epoch
        items = workqueue.build(cfg["queue"], run.only(tr.known(ctx), a.only), ledger(ctx), run.source_size(ctx),
                                limit=a.top, epoch=attempt_epoch(ctx))
        for w in items:
            print(f"{w.priority:7.2f} n={w.size:<4} {w.key}\n         e.g. {', '.join(w.tests)}")
        return 0
    if a.cmd == "doctor":
        from swarmkit import doctor
        return doctor.main(ctx, a.rest, a.run_suite)
    if a.cmd == "event":
        from swarmkit.common import event
        event(ctx, " ".join(a.rest), "note")
        return 0
    if a.cmd == "stats":
        from swarmkit import stats
        return stats.main(ctx, a.out or ctx.state.parent / "stats", a.ledger)
    if a.cmd == "cluster":
        results: dict = {}
        for p in a.rest:
            results.update(json.loads(Path(p).read_text()))
        for w in workqueue.build(cfg["queue"], results, limit=a.top):
            print(f"{w.priority:7.2f} n={w.size:<4} {w.key}\n         e.g. {', '.join(w.tests)}")
        fails = sum(1 for r in results.values() if r.get("status") not in ("PASS", "SKIP"))
        sigs = len(workqueue.clusters(results, frozenset(cfg["queue"]["keep_words"])))
        print(f"{len(results)} results, {fails} failing, {sigs} signatures", file=sys.stderr)
        return 0
    return run.run(ctx, a)


if __name__ == "__main__":
    sys.exit(main())
