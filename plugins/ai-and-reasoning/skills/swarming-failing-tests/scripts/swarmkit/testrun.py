"""Adapter around the project's test command, plus the per-commit results cache.

The test command (config `tests.command`) is the only thing the swarm knows about
the project's tests. Its contract:
    - runs the named suites (comma list in {suites}) with {jobs} parallelism,
      restricted by one `filter_args` group per test id when given;
    - writes JSON to {out}: {test_id: {status, reason, stage}};
    - test_id = "<suite>/<anything>"; status PASS passes, SKIP is ignored, anything
      else (FAIL, TIMEOUT, CRASH, ...) is failing; a test absent from the output
      did not run (MISSING: skipped or removed upstream, never a regression).
`reason` and `stage` feed the clustering, so their quality decides cluster quality.

Results cache (all under the state dir):
    results/<commit>.json   every result recorded at that main commit (partial or full)
    known.json              {test_id: {status, reason, stage, commit}}: latest status of
                            each test along main; the gate compares to this
    baseline.json           {commit, time, suites, tests_tree, suite_trees}: last full run
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import time
from pathlib import Path

from swarmkit.common import Ctx, log, read_json, write_json


def is_pass(rec: dict | None) -> bool:
    return bool(rec) and rec.get("status") == "PASS"


def suite_of(test_id: str) -> str:
    return test_id.split("/", 1)[0]


def list_suites(ctx: Ctx, tree: Path) -> list[str]:
    if ctx.tests["suites"]:
        found = list(ctx.tests["suites"])
    else:
        d = tree / ctx.tests["suites_dir"]
        found = sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []
    return [s for s in found if not ctx.suites or s in ctx.suites]


def _env(ctx: Ctx, tree: Path) -> dict:
    env = dict(os.environ)
    for k, v in ctx.tests["env"].items():
        env[k] = os.path.expandvars(str(v).replace("{tree}", str(tree)))
    return env


def _escape(ctx: Ctx, test_id: str) -> str:
    if ctx.tests["filter_escape"] == "fnmatch":
        return "".join(f"[{c}]" if c in "*?[]" else c for c in test_id)
    return test_id


def invoke(ctx: Ctx, tree: Path, suites: list[str], jobs: int, filters: list[str]) -> dict | None:
    """One test-command invocation in `tree`. Returns {test_id: rec}, or None when the command
    produced no JSON at all (a broken runner must not read as "every test is missing")."""
    with tempfile.TemporaryDirectory(prefix="swarm-tr-") as td:
        out = Path(td) / "r.json"
        sub = {"{suites}": ",".join(suites), "{jobs}": str(jobs), "{out}": str(out), "{tree}": str(tree)}
        cmd = []
        for a in ctx.tests["command"]:
            for k, v in sub.items():
                a = a.replace(k, v)
            cmd.append(a)
        for f in filters:
            cmd += [a.replace("{glob}", f) for a in ctx.tests["filter_args"]]
        try:
            p = subprocess.run(cmd, cwd=tree, env=_env(ctx, tree), capture_output=True, text=True,
                               errors="replace", timeout=ctx.tests["timeout"], check=False)
        except subprocess.TimeoutExpired:
            log(f"test command for {','.join(suites)} timed out in {tree}")
            return None
        res = read_json(out, None)
        if res is None:
            log(f"test command wrote no JSON (rc={p.returncode}): {p.stderr[-300:]}")
        return res


def run_ids(ctx: Ctx, tree: Path, ids: list[str], jobs: int | None = None) -> dict:
    """Run exactly these test ids in `tree`. Ids with no result come back as MISSING;
    when the runner itself broke they come back as ERROR (not passing, not missing)."""
    ids = sorted(set(ids))
    out: dict = {}
    for i in range(0, len(ids), 400):         # keep argv a sane length
        chunk = ids[i:i + 400]
        suites = sorted({suite_of(t) for t in chunk})
        res = invoke(ctx, tree, suites, jobs or ctx.jobs, [_escape(ctx, t) for t in chunk])
        if res is None:
            out.update({t: {"status": "ERROR", "reason": "test command failed", "stage": "harness"} for t in chunk})
            continue
        out.update({t: res[t] for t in chunk if t in res})
    for t in ids:
        out.setdefault(t, {"status": "MISSING", "reason": "no result from the test command", "stage": "run"})
    return out


def run_full(ctx: Ctx, tree: Path, suites: list[str] | None = None) -> dict:
    res: dict = {}
    for s in suites if suites is not None else list_suites(ctx, tree):
        t0 = time.time()
        r = invoke(ctx, tree, [s], ctx.jobs, []) or {}
        log(f"full run: suite {s}: {sum(map(is_pass, r.values()))}/{len(r)} pass ({time.time() - t0:.0f}s)")
        res.update(r)
    return res


# ---------------------------------------------------------------- cache

def known(ctx: Ctx) -> dict:
    return read_json(ctx.state / "known.json", {}) or {}


def record(ctx: Ctx, commit: str, results: dict, replace_known: bool = False) -> None:
    """Store results observed at `commit` and fold them into known.json."""
    path = ctx.state / "results" / f"{commit}.json"
    cur = read_json(path, {}) or {}
    cur.update(results)
    write_json(path, cur)
    k = {} if replace_known else known(ctx)
    for t, r in results.items():
        if r.get("status") == "MISSING":
            k.pop(t, None)        # skipped or removed upstream: forget it, so it is neither gated nor queued
            continue
        if r.get("status") == "ERROR":
            continue              # the runner broke: we learned nothing about this test
        k[t] = {"status": r.get("status"), "reason": r.get("reason", ""), "stage": r.get("stage", ""),
                "commit": commit}
        credit = ctx.gate.get("partial_credit")
        if credit and isinstance(r.get(credit), (int, float)):
            k[t][credit] = r[credit]
    write_json(ctx.state / "known.json", k)


def suite_counts(results: dict) -> dict:
    c: dict = {}
    for t, r in results.items():
        s = c.setdefault(suite_of(t), {"pass": 0, "total": 0})
        s["total"] += 1
        s["pass"] += is_pass(r)
    return c


def sample_ids(ctx: Ctx, n: int, seed: str, suites: set[str] | None = None) -> list[str]:
    """Fixed pseudo-random sample of known-passing tests, stable for a given seed (the baseline
    commit), optionally restricted to `suites`."""
    passing = sorted(t for t, r in known(ctx).items() if is_pass(r) and (suites is None or suite_of(t) in suites))
    return sorted(passing, key=lambda t: hashlib.sha1(f"{seed}:{t}".encode()).hexdigest())[:n]


def tests_tree(ctx: Ctx, commit: str = "HEAD") -> tuple[str, dict[str, str]]:
    """(tree hash of tests.tests_tree, {suite: tree hash} of tracked suite dirs) at `commit`."""
    from swarmkit.common import git
    whole = git(ctx.root, "rev-parse", "-q", "--verify", f"{commit}:{ctx.tests['tests_tree']}", check=False).strip()
    per: dict[str, str] = {}
    lst = git(ctx.root, "ls-tree", f"{commit}:{ctx.tests['suites_dir']}", check=False)
    for line in lst.splitlines():
        meta, _, name = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "tree":
            per[name] = parts[2]
    return whole, per


def changed_suites(ctx: Ctx) -> list[str] | None:
    """Suites to re-baseline because tests changed since the last baseline.
    [] = nothing changed; a list = only these suites (new, edited or deleted suite dirs on main,
    plus suite dirs on disk the baseline never ran, e.g. a gitignored corpus a builder just
    downloaded); None = something else in the tests tree changed (the runner): refresh everything."""
    base = read_json(ctx.state / "baseline.json", {}) or {}
    if "tests_tree" not in base:
        return []                   # baselined before tree tracking existed: nothing to compare
    ran = base.get("suite_names")
    on_disk = [s for s in list_suites(ctx, ctx.root) if ran is not None and s not in ran]
    whole, per = tests_tree(ctx)
    if not whole or whole == base["tests_tree"]:
        return sorted(on_disk)
    old = base.get("suite_trees") or {}
    diff = sorted(s for s in set(per) | set(old) if old.get(s) != per.get(s))   # new, edited, deleted
    if base.get("outside") is not None and base["outside"] != _outside(ctx):
        return None
    return sorted({s for s in diff if not ctx.suites or s in ctx.suites} | set(on_disk))


def _outside(ctx: Ctx, commit: str = "HEAD") -> dict[str, str]:
    """{path: blob/tree hash} of everything in the tests tree except the suites dir."""
    from swarmkit.common import git
    tt, sd = ctx.tests["tests_tree"].rstrip("/"), ctx.tests["suites_dir"].rstrip("/")
    out = {}
    for line in git(ctx.root, "ls-tree", "-r", "-t", commit, "--", tt, check=False).splitlines():
        meta, _, path = line.partition("\t")
        if path == sd or path.startswith(sd + "/"):
            continue
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob":
            out[path] = parts[2]
    return out


def tree_stamp(ctx: Ctx, commit: str) -> dict:
    whole, per = tests_tree(ctx, commit)
    return {"tests_tree": whole, "suite_trees": per, "outside": _outside(ctx, commit)}
