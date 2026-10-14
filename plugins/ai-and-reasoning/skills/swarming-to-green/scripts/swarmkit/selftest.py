"""Self-test of the swarm machinery on a throwaway fake project (no model calls, about 2 minutes).

    swarm.py selftest [--keep]

Builds a git repo in a temp dir whose code lives in src/ and whose fake test
command passes a test iff src/_fake_fixes/<suite>__<name> (or _all_<suite>)
exists, writes a swarm.toml for it, then drives `swarm.py run --fake` through
every gate path and asserts the ledger outcome. Each check names the 2026-10-12
failure it guards. Federation runs with a local bare repo as the transport.
Exit status is the number of failures (0 = green); read the exit code, not the tail.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from swarmkit.common import read_jsonl

CLI = Path(__file__).resolve().parents[1] / "swarm.py"

FAKE_RUN = '''"""Fake test command: a test passes iff src/_fake_fixes/<suite>__<name> or _all_<suite> exists."""
import argparse, fnmatch, json, os
from pathlib import Path
ap = argparse.ArgumentParser()
for f in ("--suite", "--jobs", "--json"): ap.add_argument(f)
ap.add_argument("--filter", action="append"); ap.add_argument("--quiet", action="store_true")
a = ap.parse_args()
root = Path(__file__).resolve().parent.parent
skip = set(filter(None, os.environ.get("FAKE_SKIP", "").split(",")))
res = {}
for suite in (a.suite or "smoke").split(","):
    d = root / "tests/suites" / suite
    if not d.is_dir(): continue
    for f in sorted(d.iterdir()):
        tid = f"{suite}/{f.name}"
        if tid in skip: continue
        if a.filter and not any(fnmatch.fnmatch(tid, x) for x in a.filter): continue
        fx = root / "src/_fake_fixes"
        ok = (fx / f"{suite}__{f.name}").exists() or (fx / f"_all_{suite}").exists()
        n = int("".join(c for c in f.name if c.isdigit()) or 0)
        if suite == "big":
            reason, stage = "undefined reference to frob_widget", "link"
        else:
            reason = ["unexpected token 'foo%d' at /abs/dir/%s:3:%d" % (n, f.name, n),
                      "unsupported node BinOp line %d" % n, "exit code %d expected 0" % n][n % 3]
            stage = ["parse", "codegen", "run"][n % 3]
        closer = (root / "src/_fake_partial" / f"{suite}__{f.name}").exists()
        res[tid] = ({"status": "PASS", "reason": "", "stage": "", "frac": 1.0} if ok else
                    {"status": "FAIL", "reason": reason, "stage": stage, "frac": 0.5 if closer else 0.0})
if a.json: Path(a.json).write_text(json.dumps(res))
'''

CONFIG = '''project = "selftest"
[tests]
command = ["{py}", "tests/run.py", "--suite", "{{suites}}", "--jobs", "{{jobs}}", "--json", "{{out}}", "--quiet"]
link_untracked = []
one_stage_ok = ["missing"]
[paths]
code = ["src/"]
allowed = ["docs/NOTES.md"]
forbidden = ["tests/"]
[queue]
ladder = [["smoke", 6], ["c-testsuite", 5]]
gate_targets = 3
[gate]
always_suites = ["smoke"]
cheap_suites = ["smoke", "c-testsuite"]
compat_command = ["{py}", "-m", "compileall", "-q", "{{tree}}/src"]
coauthor = ""
partial_credit = "frac"
[git]
author_name = "Swarm Selftest"
author_email = "selftest@example.invalid"
[worker]
scratch = "{scratch}/{{id}}"
repro_command = "python3 tests/run.py --suite {{suite}} --filter '{{test}}' --jobs 1"
deny = ["Bash(curl:*)", "WebFetch"]
[run]
min_free_gb = 0.2
[federation]
prefix = "swarm/"
'''


def sh(cwd: Path, *cmd: str) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def build_repo(root: Path, scratch: Path) -> None:
    for suite, n in (("smoke", 4), ("c-testsuite", 12), ("gcc-torture", 18), ("big", 30)):
        d = root / "tests" / "suites" / suite
        d.mkdir(parents=True)
        for i in range(1, n + 1):
            (d / f"{suite[0]}{i}.c").write_text("int main(){return 0;}\n")
    fixes = root / "src" / "_fake_fixes"
    fixes.mkdir(parents=True)
    for name in [f"smoke__s{i}.c" for i in range(1, 5)] + [f"c-testsuite__c{i}.c" for i in range(1, 7)]:
        (fixes / name).write_text("fixed\n")
    (root / "tests" / "run.py").write_text(FAKE_RUN)
    (root / "docs").mkdir()
    (root / "docs" / "NOTES.md").write_text("# notes\n")
    (root / "swarm.toml").write_text(CONFIG.format(py=sys.executable, scratch=scratch))
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "add", "-A")
    sh(root, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")


def cli(repo: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI), *args, "--root", str(repo)], capture_output=True, text=True,
                          timeout=600, check=False, env={**os.environ, **(env or {})})


def run(repo: Path, wt: Path, *args: str, env: dict | None = None) -> str:
    p = cli(repo, "run", "--fake", "--wt-root", str(wt), "--poll", "0.3", "--sample", "4", "--idle-max", "5",
            "--full-every", "99", "--quick-every", "0", "--sweep-lag", "0", "--no-idle-refresh", *args, env=env)
    return p.stdout + p.stderr


def records(repo: Path) -> dict[str, dict]:
    last: dict[str, dict] = {}
    for r in read_jsonl(repo / ".swarm" / "state" / "ledger.jsonl"):
        last[r["id"]] = r
    return last


def known(repo: Path) -> dict:
    return json.loads((repo / ".swarm" / "state" / "known.json").read_text())


def federation(tmp: Path, root: Path, wt: Path, expect) -> None:
    """Hub `root` + sibling clone `sib` talking through the bare repo `bare`."""
    bare, sib, swt = tmp / "remote.git", tmp / "sib", tmp / "wt-s1"
    sh(tmp, "git", "init", "-q", "--bare", str(bare))
    F = ("--fed-remote", str(bare))

    def remote(ref: str) -> str:
        return subprocess.run(["git", "rev-parse", "-q", "--verify", ref], cwd=bare, capture_output=True,
                              text=True, check=False).stdout.strip()

    def hub_ingest() -> str:
        return run(root, wt, "--federate", "--no-launch", "--fed-poll", "0", "--suites", "smoke,c-testsuite", *F)

    def sibling(*extra: str) -> str:
        return run(sib, swt, "--sibling", "s1", "--only", "gcc-torture/*", "--suites", "smoke,c-testsuite,gcc-torture",
                   *F, *extra)

    p = cli(root, "fed-publish", *F)
    out = p.stdout + p.stderr
    state_files = sh(bare, "git", "ls-tree", "--name-only", "-r", "swarm/state") if remote("swarm/state") else ""
    expect("hub publishes swarm/main and swarm/state",
           remote("swarm/main") == sh(root, "git", "rev-parse", "main").strip()
           and "federation/known.json" in state_files, out)

    sh(tmp, "git", "clone", "-q", "-b", "swarm/main", str(bare), str(sib))
    sh(sib, "git", "checkout", "-q", "-b", "fed-s1")
    out = sibling("--max-workers", "2", "--concurrency", "2")
    st = {k: v["status"] for k, v in records(sib).items()}
    tip = remote("swarm/cand/s1")
    msg = sh(sib, "git", "log", "-1", "--format=%B", tip) if tip else ""
    expect("sibling seeds from swarm/state, merges locally, pushes swarm/cand/s1 with a Fixed: trailer",
           st.get("s1-w00001") == "merged" and st.get("s1-w00002") == "merged" and "Fixed: gcc-torture/" in msg, out)

    out = hub_ingest()
    hst = {k: v["status"] for k, v in records(root).items()}
    expect("hub ingests both candidates, merges them and pushes swarm/main",
           hst.get("s1-w00001") == "merged" and hst.get("s1-w00002") == "merged"
           and remote("swarm/main") == sh(root, "git", "rev-parse", "main").strip(), out)

    old_tip = remote("swarm/cand/s1")
    out = sibling("--max-workers", "1", "--concurrency", "1", "--fake-mode", "conflict")
    new_tip = remote("swarm/cand/s1")
    stack = sh(sib, "git", "rev-list", "--first-parent", "--no-merges", new_tip, "^" + remote("swarm/main")).split()
    ff = subprocess.run(["git", "merge-base", "--is-ancestor", old_tip, new_tip], cwd=bare, check=False).returncode == 0
    expect("sibling rebase drops hub-merged commits; swarm/cand/s1 only fast-forwards (no branch is ever deleted)",
           records(sib).get("s1-w00003", {}).get("status") == "merged" and len(stack) == 1 and ff, out)

    (root / "src" / "_fake_conflict.txt").write_text("hub change\n")
    sh(root, "git", "add", "-A")
    sh(root, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "hub: conflicting change")
    out = hub_ingest()
    r = records(root).get("s1-w00003") or {}
    expect("hub: conflicting candidate rejected as a conflict (once per sha)",
           r.get("status") == "rejected" and str(r.get("reason", "")).startswith("conflict"), out)

    out = sibling("--no-launch")
    r = records(sib).get("s1-w00003") or {}
    expect("sibling rebase drops the conflicting commit and marks it a conflict",
           r.get("status") == "rejected" and str(r.get("reason", "")).startswith("conflict"), out)

    out = sibling("--max-workers", "1", "--concurrency", "1", "--only", ",".join(r.get("tests") or []))
    r4 = records(sib).get("s1-w00004") or {}
    out += hub_ingest()
    expect("conflicted cluster re-dispatched as a REBASE worker (not counted as a failure), then ingested",
           r4.get("rebase_of") == "s1-w00003" and r4.get("effort") != "high"
           and records(root).get("s1-w00004", {}).get("status") == "merged", out)

    p = cli(sib, "fed-export-ledger", "s1", *F)
    files = sh(bare, "git", "ls-tree", "-r", "--name-only", "swarm/stats/s1") if remote("swarm/stats/s1") else ""
    expect("stand-down: sibling ledger exported to swarm/stats/s1", "federation/ledger.jsonl" in files,
           p.stdout + p.stderr)


def quick(root: Path, wt: Path, expect) -> None:
    """Tiered quick refresh: a regression the gate sample missed is caught by the next quick refresh
    and bisected over the merges since the previous one only (2026-10-12: a full refresh after 200
    merges found 82 regressions whose culprit sat 256 commits back and could not be reverted)."""
    failing = sorted(t for t, v in known(root).items() if v["status"] != "PASS" and not t.startswith("big/"))
    Q = ("--max-workers", "1", "--concurrency", "1", "--quick-every", "1", "--quick-suites", "smoke,big")
    before = set(records(root))
    out = run(root, wt, *Q, "--only", failing[0])
    new = [r for k, r in records(root).items() if k not in before]
    expect("quick refresh runs after a merge (--quick-every 1) and completes",
           new and new[0]["status"] == "merged" and "quick refresh at" in out and "quick refresh done" in out, out)
    # break deletes the first other fix marker, _all_big: big regresses; --sample 0 lets it past the gate
    before = set(records(root))
    out = run(root, wt, *Q, "--only", failing[1], "--fake-mode", "break", "--sample", "0")
    new = [r for k, r in records(root).items() if k not in before]
    stale = [t for t, v in known(root).items() if t.startswith("big/") and v["status"] != "PASS"]
    expect("regression the gate sample missed -> quick refresh bisects over 1 merge (not since the full "
           "baseline) and reverts it",
           new and new[0]["status"] == "reverted" and "bisect over 1 swarm merges" in out and not stale, out)
    p = cli(root, "status", "--quick-suites", "smoke,big")
    expect("status prints the quick refresh line", "quick refresh: every" in p.stdout
           and "1 reverted, 0 left" in p.stdout, p.stdout + p.stderr)


def sweep(root: Path, wt: Path, expect) -> None:
    """Rotating sweep: with quick refresh off and the gate sample at 0, a regression in a suite the gate
    never runs is caught by the sweep step for that suite, bisected over the merges since that suite last
    ran on main, and reverted (2026-10-13 haiku-cc: Mbed TLS broken for 14 h, TinyCC 333 -> 35, because no
    refresh after the culprit ran those suites)."""
    failing = sorted(t for t, v in known(root).items() if v["status"] != "PASS" and not t.startswith("big/"))
    before = set(records(root))
    # break deletes _all_big: every big/ test regresses; nothing in the gate runs big/
    out = run(root, wt, "--max-workers", "1", "--concurrency", "1", "--only", failing[0], "--fake-mode", "break",
              "--sample", "0", "--sweep-lag", "1")
    new = [r for k, r in records(root).items() if k not in before]
    broken = [t for t, v in known(root).items() if t.startswith("big/") and v["status"] != "PASS"]
    sw = json.loads((root / ".swarm" / "state" / "sweep.json").read_text())
    expect("sweep: a regression in a suite the gate never ran is caught by that suite's sweep step and reverted",
           bool(new) and new[0]["status"] == "reverted" and "sweep big at" in out and not broken, out)
    expect("sweep: every owned suite ran on main since the last merge (sweep.json, lag 0)",
           all(sw.get(x, {}).get("merges_total") == json.loads((root / ".swarm/state/counters.json").read_text())
               ["merges_total"] for x in ("smoke", "c-testsuite", "gcc-torture", "big", "extra")), json.dumps(sw)[:800])
    p = cli(root, "status", "--sweep-lag", "1")
    expect("status prints the sweep line", "sweep: every suite on main within 1 merges" in p.stdout
           and "worst lag 0" in p.stdout, p.stdout + p.stderr)


def base_check(root: Path, wt: Path, expect) -> None:
    """Base check: a test fixed on main outside the swarm (or by another cluster's merge) still reads FAIL
    in known.json at an older commit. The dispatcher re-runs the item's tests at HEAD before launching and
    spends no worker (2026-10-12: ~100 ghost workers on QuickJS; sibling s2: 40 workers, 0 merges)."""
    t = sorted(x for x, v in known(root).items() if v["status"] != "PASS" and not x.startswith("big/"))[-1]
    (root / "src" / "_fake_fixes" / t.replace("/", "__")).write_text("fixed\n")
    sh(root, "git", "add", "-A")
    sh(root, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "another fix outside the swarm")
    before = set(records(root))
    out = run(root, wt, "--only", t, "--max-workers", "1", "--concurrency", "1")
    new = [r for k, r in records(root).items() if k not in before]
    head = sh(root, "git", "rev-parse", "main").strip()
    k = known(root).get(t, {})
    expect("base check: an item whose test already passes at HEAD launches no worker; known.json updated at HEAD",
           not new and "BASE-CHECK" in out and k.get("status") == "PASS" and k.get("commit") == head, out)
    p = cli(root, "status")
    expect("status prints the base check line", "base check:" in p.stdout and "not launched" in p.stdout,
           p.stdout + p.stderr)


def near_hold(tmp: Path, expect) -> None:
    """Near-hold: a rebase whose patch modifies a file a live peer is changing waits; a peer that only
    adds files, or a conflict older than queue.near_hold_s, does not hold it (haiku-cc ledgers: 31 of
    43 rebases launched next to such a peer conflicted again, 1 of 11 without one)."""
    from swarmkit import config as cfgmod
    from swarmkit import nearness
    from swarmkit.common import Ctx
    cfg = cfgmod.load(None)
    cfg["state_dir"] = str(tmp / "nh-state")
    ctx = Ctx(tmp, cfg, wt_root=tmp / "nh-wt")
    mod = "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-x\n+y\n"
    add = "diff --git a/src/new.py b/src/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/src/new.py\n@@ -0,0 +1 @@\n+z\n"
    now = time.time()
    led = {"c1": {"id": "c1", "signature": "S", "status": "rejected", "reason": "conflict applying onto main",
                  "t_gate": now - 60},
           "p1": {"id": "p1", "signature": "T", "status": "finished"},
           "p2": {"id": "p2", "signature": "U", "status": "finished"}}
    (ctx.task_dir("c1") / "patch.diff").write_text(mod)
    (ctx.task_dir("p1") / "patch.diff").write_text(mod.replace("+y", "+w"))
    (ctx.task_dir("p2") / "patch.diff").write_text(add)
    live = nearness.live_files(ctx, led)
    held = nearness.hold(ctx, led, "S", live, now)
    expect("near-hold: rebase waits for the peer modifying its file, not for one adding a new file",
           held == ["p1"] and nearness.patch_files(add) == set(), f"{held} {live}")
    late = nearness.hold(ctx, led, "S", live, now + cfg["queue"]["near_hold_s"] + 1)
    expect("near-hold: dispatches anyway once near_hold_s has passed since the conflict; first attempts never wait",
           late == [] and nearness.hold(ctx, led, "T", live, now) == [], f"{late}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", action="store_true", help="keep the temp repo for inspection")
    a = ap.parse_args(argv)
    tmp = Path(tempfile.mkdtemp(prefix="swarm-selftest-"))
    root, wt, scratch = tmp / "repo", tmp / "wt", tmp / "scratch"
    root.mkdir()
    build_repo(root, scratch)
    failures: list[str] = []

    def expect(name: str, ok: bool, out: str) -> None:
        print(f"{'ok  ' if ok else 'FAIL'} {name}", flush=True)
        if not ok:
            failures.append(name)
            print(out[-3000:])

    def st(i: int) -> str:
        return (records(root).get(f"w{i:05d}") or {}).get("status", "")

    p = cli(root, "doctor", "--run-suite", "gcc-torture")
    expect("doctor accepts the test command's JSON contract", p.returncode == 0 and "doctor: ok" in p.stdout, p.stdout + p.stderr)
    stubs = tmp / "stubs.json"
    stubs.write_text(json.dumps({f"tu{i % 4}/f{i}": {"status": "FAIL", "stage": "missing",
                                                      "reason": f"stub: not yet written in tu{i % 4}"} for i in range(60)}))
    p = cli(root, "doctor", str(stubs))
    expect("doctor does not flag a stage that tests.one_stage_ok says may hold every failure "
           "(2026-10-13 swarm-decomp: one 'missing' stub per function)",
           p.returncode == 0 and "WARN" not in p.stdout and "one_stage_ok" in p.stdout, p.stdout + p.stderr)

    out = run(root, wt, "--max-workers", "2", "--concurrency", "2")
    expect("fix -> merged", st(1) == "merged" and st(2) == "merged", out)
    task = json.loads((root / ".swarm" / "state" / "tasks" / "w00001" / "task.jsonl").read_text().splitlines()[0])
    expect("worker.deny reaches the task (2026-10-13 swarm-decomp: workers allowed Bash kept off the network)",
           task.get("deny") == ["Bash(curl:*)", "WebFetch"], json.dumps(task)[:500])
    scraps = list(scratch.glob("w*")) if scratch.exists() else []
    expect("worker scratch deleted on reap (2026-10-12: 14 GB of /tmp filled the disk)", not scraps, out)
    out = run(root, wt, "--fake-mode", "tests", "--max-workers", "1", "--concurrency", "1")
    expect("edit under a forbidden path -> rejected", st(3) == "rejected", out)
    out = run(root, wt, "--fake-mode", "syntax", "--max-workers", "1", "--concurrency", "1")
    r = records(root).get("w00004") or {}
    expect("code that fails the compat command -> rejected",
           r.get("status") == "rejected" and str(r.get("reason", "")).startswith("compat check:"), out)
    out = run(root, wt, "--fake-mode", "noop", "--max-workers", "1", "--concurrency", "1")
    expect("noop -> failed", st(5) == "failed", out)
    out = run(root, wt, "--fake-mode", "break", "--max-workers", "1", "--concurrency", "1", "--full-every", "1")
    expect("regression -> rejected by the gate sample or reverted by the refresh", st(6) in ("rejected", "reverted"), out)
    out = run(root, wt, "--fake-mode", "conflict", "--max-workers", "2", "--concurrency", "2", "--batch", "2", "--poll", "2")
    pair = sorted([st(7), st(8)])
    expect("conflicting pair -> one merged, one rejected as a conflict", pair == ["merged", "rejected"], out)
    out = run(root, wt, "--fake-mode", "docs", "--max-workers", "2", "--concurrency", "2", "--batch", "2", "--poll", "2")
    expect("conflicting best-effort doc edits -> both merged (code only for one)",
           st(9) == "merged" and st(10) == "merged", out)
    out = run(root, wt, "--fake-mode", "latin1", "--max-workers", "1", "--concurrency", "1")
    expect("non-UTF-8 bytes in a diff -> merged, loop alive (surrogateescape)", st(11) == "merged", out)

    q = cli(root, "queue", "--only", "big/*").stdout
    expect("a concrete signature (one root cause) is not sharded", q.count("frob_widget") == 1 and "#1/" not in q, q)
    out = run(root, wt, "--fake-mode", "shared", "--only", "big/*", "--max-workers", "1", "--concurrency", "1")
    k = known(root)
    stale = [t for t, v in k.items() if t.startswith("big/") and v["status"] != "PASS"]
    expect("after a shared-root fix the whole cluster is re-checked (no stale FAILs; 2026-10-12: ~100 ghost workers)",
           st(12) == "merged" and not stale and len([t for t in k if t.startswith("big/")]) == 30, out)

    out = run(root, wt, "--fake-mode", "fix", "--max-workers", "1", "--concurrency", "1",
              env={"FAKE_SKIP": "smoke/s1.c"})
    expect("a test that stops running (skip list) is not a regression and leaves known.json "
           "(2026-10-12: 27 good patches rejected)", st(13) == "merged" and "smoke/s1.c" not in known(root), out)

    for _ in range(2):
        run(root, wt, "--fake-mode", "noop", "--only", "gcc-torture/g7.c", "--max-workers", "1", "--concurrency", "1")
    out = run(root, wt, "--only", "gcc-torture/g7.c", "--max-workers", "1", "--concurrency", "1")
    r = records(root).get("w00016") or {}
    expect("after 2 real failures: feature mode at high effort (effort ladder), then merged",
           records(root).get("w00014", {}).get("effort") is None and records(root).get("w00015", {}).get("effort") == "high"
           and r.get("feature") and r.get("effort") == "high" and r.get("status") == "merged", out)

    for _ in range(3):
        run(root, wt, "--fake-mode", "noop", "--only", "gcc-torture/g8.c", "--max-workers", "1", "--concurrency", "1")
    parked = cli(root, "queue", "--only", "gcc-torture/g8.c").stdout
    cli(root, "unpark")
    after = cli(root, "queue", "--only", "gcc-torture/g8.c").stdout
    expect("3 failed attempts park a test; `unpark` (attempt epoch) makes it dispatchable again",
           "g8.c" not in parked and "g8.c" in after, parked + after)

    (wt / "w00001").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "suites" / "extra").mkdir()
    for i in (1, 2):
        (root / "tests" / "suites" / "extra" / f"e{i}.c").write_text("int main(){return 1;}\n")
    sh(root, "git", "add", "-A")
    sh(root, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "tests: new suite extra")
    hist = len(read_jsonl(root / ".swarm" / "state" / "history.jsonl"))
    out = run(root, wt, "--only", "extra/*", "--max-workers", "1", "--concurrency", "1")
    newrec = [r for r in records(root).values() if any(t.startswith("extra/") for t in r.get("tests", []))]
    expect("a new suite committed to main is baselined alone (no full refresh) and dispatched",
           newrec and newrec[0]["status"] == "merged"
           and len(read_jsonl(root / ".swarm" / "state" / "history.jsonl")) == hist, out)
    expect("stale worktree of an ended worker swept at start (2026-10-12: 5.6 GB)", not (wt / "w00001").exists(), out)

    gate = wt / "_gate"
    orphan = subprocess.Popen(["sleep", "120"], cwd=gate)
    p = cli(root, "stop", "--wt-root", str(wt))
    time.sleep(0.5)
    expect("`stop` kills test processes left running in the gate tree (2026-10-12: orphans held 4 cores)",
           orphan.poll() is not None, p.stdout + p.stderr)

    federation(tmp, root, wt, expect)
    quick(root, wt, expect)
    sweep(root, wt, expect)
    # stale: main already passes a test the record still marks failing; the worker says "stale" and
    # the loop re-measures the cluster at main (2026-10-12: 104 such tests, 25 workers spent on them)
    stale_t = sorted(t for t, v in known(root).items() if v["status"] != "PASS" and t.startswith("gcc-torture/"))[-1]
    (root / "src" / "_fake_fixes" / stale_t.replace("/", "__")).write_text("fixed\n")
    sh(root, "git", "add", "-A")
    sh(root, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "fix outside the swarm")
    cli(root, "unpark")
    before = set(records(root))
    out = run(root, wt, "--fake-mode", "stale", "--only", stale_t, "--max-workers", "1", "--concurrency", "1",
              "--no-base-check")       # the worker-side path; the dispatcher-side check is base_check()
    new = [r for k, r in records(root).items() if k not in before]
    expect("worker reports stale -> its cluster is re-measured at main, test now PASS, no attempt counted",
           bool(new) and new[0]["status"] == "stale" and known(root).get(stale_t, {}).get("status") == "PASS", out)
    base_check(root, wt, expect)
    near_hold(tmp, expect)
    cf = root / ".swarm" / "state" / "counters.json"
    c = json.loads(cf.read_text()) if cf.exists() else {}
    c["merges_since_full"] = 3                  # merges the gate checked only against its sample
    cf.write_text(json.dumps(c))
    out = run(root, wt, "--idle-refresh", "--only", "nothing/*", "--max-workers", "1", "--concurrency", "1")
    expect("queue drained with unrefreshed merges -> full refresh before idling (2026-10-12: late regressions "
           "after the last refresh shipped, TinyCC 333 -> 35)",
           "merges since the last full refresh, refreshing" in out
           and json.loads(cf.read_text()).get("merges_since_full") == 0, out)
    cli(root, "unpark")
    pt = sorted(t for t, v in known(root).items() if v["status"] != "PASS" and not t.startswith("big/"))[0]
    before = set(records(root))
    out = run(root, wt, "--fake-mode", "partial", "--only", pt, "--max-workers", "1", "--concurrency", "1")
    new = [r for k, r in records(root).items() if k not in before]
    expect("partial credit: a 'partial' worker that raises the targets' frac with no regression is merged "
           "without a flip (2026-10-13 swarm-decomp: 125 partials, 39% of spend, discarded)",
           bool(new) and new[0]["status"] == "merged" and not new[0].get("gate_fixed")
           and new[0].get("partial_gain", 0) >= 0.05 and known(root).get(pt, {}).get("frac") == 0.5, out)
    before = set(records(root))
    out = run(root, wt, "--fake-mode", "partial", "--only", pt, "--max-workers", "1", "--concurrency", "1")
    new = [r for k, r in records(root).items() if k not in before]
    expect("partial credit: no rise in frac -> not merged",
           bool(new) and new[0]["status"] != "merged", out)
    from swarmkit.run import pick_effort
    lad = ["", "high", "xhigh", "max"]
    picks = [pick_effort(lad, n, False, "xhigh", "") for n in range(5)] + [pick_effort(lad, 0, True, "xhigh", ""),
             pick_effort(lad, 3, True, "xhigh", ""), pick_effort(["", "high"], 0, True, "high", "")]
    expect("effort ladder climbs past high to xhigh and max; feature work never below feature_effort",
           picks == ["", "high", "xhigh", "max", "max", "xhigh", "max", "high"], str(picks))
    from swarmkit.run import projected_spend
    led = {"a": {"status": "merged", "cost_usd": 0.10, "t_done": 1}, "b": {"status": "failed", "cost_usd": 0.30, "t_done": 2},
           "c": {"status": "merged", "cost_usd": 2.0, "t_done": 3, "feature": True},
           "d": {"status": "launched"}, "e": {"status": "launched", "feature": True}}
    ps = projected_spend(led)
    expect("--max-usd counts in-flight workers at the recent mean cost (2026-10-13: a $36 cap overran by $5)",
           abs(ps - (2.4 + 0.2 + 2.0)) < 1e-9, f"projected {ps}")
    log = sh(root, "git", "log", "--format=%an|%B")
    expect("merge commits carry the configured author and Swarm-Task trailers",
           "Swarm Selftest|" in log and "Swarm-Task: w00001" in log, "")
    p = cli(root, "status")
    expect("status prints the check-in signals block", "SIGNALS:" in p.stdout, p.stdout + p.stderr)
    p = cli(root, "stats", "--out", str(tmp / "stats"))
    expect("stats writes metrics.json and report.md", (tmp / "stats" / "metrics.json").exists()
           and (tmp / "stats" / "report.md").exists(), p.stdout + p.stderr)
    print(f"{len(failures)} failures" + (f": {failures}" if failures else ""))
    if a.keep:
        print(f"kept {tmp}")
    else:
        subprocess.run(["git", "worktree", "prune"], cwd=root, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
    return min(len(failures), 100)
