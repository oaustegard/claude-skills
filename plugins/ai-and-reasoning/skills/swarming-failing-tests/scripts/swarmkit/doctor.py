"""Check the test command's output before a swarm depends on it.

    swarm.py doctor [RESULTS.json ...] [--run-suite smoke]

Clustering quality is decided by the runner: a broken stage regex that labels
every failure "parse", or reasons truncated with the file:line prefix still in
front, collapse or scatter the clusters, and the swarm then dispatches the wrong
work for hours. Diagnosed 2026-10-12 on haiku-cc, both cases. This reads a
results file (default: known.json), or runs one suite through the configured
command, and reports contract violations and the clustering it would produce.
Exit 1 on a contract violation, 0 otherwise (warnings print but pass).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from swarmkit import testrun as tr
from swarmkit import workqueue
from swarmkit.common import Ctx


def check(ctx: Ctx, results: dict) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    if not isinstance(results, dict) or not results:
        return ["results are empty or not a JSON object {test_id: {status, reason, stage}}"], []
    bad_ids = [t for t in results if "/" not in t]
    if bad_ids:
        errs.append(f"{len(bad_ids)} test ids lack the '<suite>/' prefix (e.g. {bad_ids[0]!r})")
    bad_rec = [t for t, r in results.items() if not isinstance(r, dict) or "status" not in r]
    if bad_rec:
        errs.append(f"{len(bad_rec)} records lack a status (e.g. {bad_rec[0]!r})")
    fails = {t: r for t, r in results.items() if isinstance(r, dict) and r.get("status") not in ("PASS", "SKIP")}
    statuses = Counter(r.get("status") for r in results.values() if isinstance(r, dict))
    print(f"{len(results)} results: " + ", ".join(f"{k} {v}" for k, v in statuses.most_common()))
    if not fails:
        warns.append("no failing tests: nothing to dispatch (build failing-test supply first)")
        return errs, warns
    stages = Counter(r.get("stage") or "" for r in fails.values())
    top_stage, n_top = stages.most_common(1)[0]
    print("failure stages: " + ", ".join(f"{k or '<empty>'} {v}" for k, v in stages.most_common(8)))
    if len(fails) >= 20 and n_top > 0.9 * len(fails):
        warns.append(f"{n_top}/{len(fails)} failures have stage '{top_stage}': check the runner's stage "
                     "detection on a few by hand (a broken regex labelled everything 'parse' on 2026-10-12)")
    empty = sum(1 for r in fails.values() if not (r.get("reason") or "").strip())
    if empty > 0.2 * len(fails):
        warns.append(f"{empty}/{len(fails)} failures have an empty reason: they all land in one cluster")
    def last(r: dict) -> str:
        lines = (r.get("reason") or "").strip().splitlines()
        return lines[-1] if lines else ""
    located = sum(1 for r in fails.values()
                  if re.match(r"\s*(/[\w.+-]+)+(:\d+)+", last(r)) and last(r).rstrip().endswith("..."))
    if located > 0.1 * len(fails):
        warns.append(f"{located} reasons start with an absolute path:line and are truncated ('...'): the "
                     "runner cut the message, not the location; strip locations before truncating")
    keep = frozenset(ctx.cfg["queue"]["keep_words"])
    cl = workqueue.clusters(results, keep)
    sizes = sorted((len(v) for v in cl.values()), reverse=True)
    print(f"{len(fails)} failing tests -> {len(cl)} signatures; largest {sizes[:5]}")
    if len(cl) > 0.8 * len(fails) and len(fails) >= 30:
        warns.append("almost one signature per test: reasons carry unmasked specifics (ids, values); "
                     "add masking-friendly reasons or queue.keep_words")
    if sizes and sizes[0] > 0.5 * len(fails) and len(fails) >= 30:
        warns.append("one signature holds over half the failures: reasons are too generic to separate causes")
    for sig, tids in sorted(cl.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"  {len(tids):5d}  {sig[:100]}")
    return errs, warns


def main(ctx: Ctx, files: list[str], run_suite: str) -> int:
    results: dict = {}
    if run_suite:
        res = tr.invoke(ctx, ctx.root, [run_suite], ctx.jobs, [])
        if res is None:
            print(f"FAIL: the test command wrote no JSON for suite {run_suite} (see the log line above)")
            return 1
        results.update(res)
    for f in files:
        results.update(json.loads(Path(f).read_text()))
    if not run_suite and not files:
        results = tr.known(ctx)
    errs, warns = check(ctx, results)
    for w in warns:
        print(f"WARN: {w}")
    for e in errs:
        print(f"FAIL: {e}")
    print("doctor: " + ("contract violations" if errs else "ok"))
    return 1 if errs else 0
