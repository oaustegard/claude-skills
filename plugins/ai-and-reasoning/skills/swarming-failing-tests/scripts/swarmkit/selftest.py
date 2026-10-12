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
        res[tid] = {"status": "PASS", "reason": "", "stage": ""} if ok else {"status": "FAIL", "reason": reason, "stage": stage}
if a.json: Path(a.json).write_text(json.dumps(res))
'''

CONFIG = '''project = "selftest"
[tests]
command = ["{py}", "tests/run.py", "--suite", "{{suites}}", "--jobs", "{{jobs}}", "--json", "{{out}}", "--quiet"]
link_untracked = []
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
[git]
author_name = "Swarm Selftest"
author_email = "selftest@example.invalid"
[worker]
scratch = "{scratch}/{{id}}"
repro_command = "python3 tests/run.py --suite {{suite}} --filter '{{test}}' --jobs 1"
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
            "--full-every", "99", *args, env=env)
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

    out = run(root, wt, "--max-workers", "2", "--concurrency", "2")
    expect("fix -> merged", st(1) == "merged" and st(2) == "merged", out)
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
