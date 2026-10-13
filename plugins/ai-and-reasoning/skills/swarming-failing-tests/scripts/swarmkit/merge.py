"""Serial merge gate: worker worktree -> tested commit on main, or rejection.

Per candidate: diff its worktree against its base commit (paths.code must apply;
paths.allowed are applied best effort and dropped on conflict; any edit under
paths.forbidden rejects the candidate), 3-way apply onto current main in the
gate worktree (wt_root/_gate), run gate.compat_command, commit with the worker's
root_cause as subject. Up to gate.batch candidates are stacked and tested once:
    gate.always_suites + every candidate's targets + a fixed sample of known-passing
    tests (seeded by the baseline commit; on a federated node, its own suites plus
    gate.cheap_suites).
Zero regressions against known.json are required, and each candidate must flip
at least one of its targets to PASS. A regressing batch is re-gated one by one.
Accepted commits fast-forward main, then every known-failing member of each
merged cluster is re-run (recheck_clusters), so known.json never keeps stale FAILs.

refresh() runs every suite at main HEAD. Tests that were PASS and now fail are
bisected over swarm merge commits and the culprit is reverted. quick_refresh() does the
same for gate.quick_suites every gate.quick_every merges, bisecting only over the merges
since the previous quick (or full) refresh, so a culprit the gate sample missed is still
recent enough to revert cleanly.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

from swarmkit import testrun as tr
from swarmkit import workqueue
from swarmkit.common import (
    Ctx,
    GitError,
    add_worktree,
    append_jsonl,
    event,
    git,
    head,
    ledger,
    ledger_put,
    link_untracked,
    log,
    quarantined,
    read_json,
    read_jsonl,
    write_json,
)

# ---------------------------------------------------------------- candidate diff

def classify(ctx: Ctx, changed: list[str], is_link=lambda f: False) -> tuple[list[str], list[str]]:
    """(forbidden edits, files to take). Files outside code/allowed are silently left behind."""
    bad = [f for f in changed if ctx.under(f, "forbidden") and not is_link(f)]
    junk = tuple(ctx.paths["junk"])
    files = [f for f in changed if (ctx.under(f, "code") or ctx.under(f, "allowed"))
             and not any(j in f for j in junk)]
    return bad, files


def candidate_patch(ctx: Ctx, rec: dict) -> tuple[str, list[str], str | None]:
    """(patch, files, error). Cached in the task dir so a removed worktree can still be merged."""
    tdir = ctx.task_dir(rec["id"])
    cached = tdir / "patch.diff"
    if cached.exists():
        return cached.read_text(errors="surrogateescape"), read_json(tdir / "patch_files.json", []), None
    wt = ctx.worktree(rec["id"])
    if not wt.exists():
        return "", [], "worktree missing"
    git(wt, "add", "-A")
    changed = [f for f in git(wt, "diff", "--cached", "--no-renames", "--name-only", rec["base"]).splitlines() if f]
    # symlinks are the orchestrator's links to untracked suites (common.link_untracked)
    bad, files = classify(ctx, changed, lambda f: (wt / f).is_symlink())
    if bad:
        return "", changed, f"edited forbidden paths: {', '.join(bad[:5])}"
    if not any(ctx.under(f, "code") for f in files):
        return "", changed, f"empty diff (no changes under {', '.join(ctx.paths['code'])})"
    # --no-renames: a rename would list only the new path and drop the deletion
    patch = git(wt, "diff", "--cached", "--no-renames", "--binary", rec["base"], "--", *files)
    if re.search(r"^\+(<{7}|>{7}) ", patch, re.MULTILINE) or re.search(r"^\+={7}$", patch, re.MULTILINE):
        return "", changed, "unresolved conflict markers in the diff"
    cached.write_text(patch, errors="surrogateescape")
    write_json(tdir / "patch_files.json", files)
    return patch, files, None


# ---------------------------------------------------------------- gate tree

def prepare_gate(ctx: Ctx, commit: str) -> Path:
    g = ctx.gate_tree
    if not (g / ".git").exists():
        add_worktree(ctx, g, commit)
    else:
        git(g, "reset", "--hard", "-q")
        git(g, "checkout", "--detach", "--force", "-q", commit)
        git(g, "clean", "-fdq")             # untracked only: gitignored suites/tools survive
        link_untracked(ctx, g)
    return g


def compat_check(ctx: Ctx, g: Path) -> str | None:
    """gate.compat_command in the gate tree (syntax / language-version gate). Returns the first
    error line, or None when it passes or none is configured. Preflight checks it exists."""
    cmd = [a.replace("{tree}", str(g)) for a in ctx.gate["compat_command"]]
    if not cmd:
        return None
    try:
        p = subprocess.run(cmd, cwd=g, capture_output=True, text=True, errors="replace", timeout=600, check=False)
    except subprocess.TimeoutExpired:
        return "compat check timed out"
    if p.returncode == 0:
        return None
    lines = [x.strip() for x in (p.stdout + "\n" + p.stderr).splitlines() if x.strip()]
    first = next((x for x in lines if "SyntaxError" in x or "IndentationError" in x),
                 next((x for x in lines if "rror" in x), lines[0] if lines else f"exit {p.returncode}"))
    return first[:240]


def split_patch(ctx: Ctx, patch: str) -> tuple[str, str]:
    """(code part, best-effort part) of a git diff, split per file."""
    code, extra = [], []
    for chunk in re.split(r"(?m)^(?=diff --git )", patch):
        if chunk.strip():
            m = re.match(r"diff --git a/(\S+)", chunk)
            (extra if m and not ctx.under(m.group(1), "code") else code).append(chunk)
    return "".join(code), "".join(extra)


def commit_patch(ctx: Ctx, g: Path, rec: dict, patch: str) -> str | None:
    """Apply + commit in the gate tree; returns the new sha or None on conflict.
    Best-effort (doc) edits go first and are dropped, not fatal, if they conflict."""
    code, extra = split_patch(ctx, patch)
    if extra:
        try:
            git(g, "apply", "--3way", "--index", "--whitespace=nowarn", "-", input=extra)
        except GitError:
            git(g, "reset", "--hard", "-q")
            log(f"note   {rec['id']}: best-effort edits conflict with main; merging code only")
    try:
        git(g, "apply", "--3way", "--index", "--whitespace=nowarn", "-", input=code)
    except GitError as e:
        git(g, "reset", "--hard", "-q")
        errs = [x for x in str(e).splitlines() if x.startswith("error:")]
        rec["reason"] = f"conflict applying onto main: {'; '.join(errs[:3])[:300] or str(e).split('): ', 1)[-1][:300]}"
        return None
    res = rec.get("result") or {}
    subject = (res.get("root_cause") or rec["signature"]).strip().splitlines()[0][:72]
    body = (f"{subject}\n\nSwarm-Task: {rec['id']}\nCluster: {rec['signature']}\n"
            f"Tests: {', '.join(res.get('test_ids_fixed') or rec['tests'])}\n")
    if ctx.gate["coauthor"]:
        body += f"\nCo-Authored-By: {ctx.gate['coauthor']}\n"
    git(g, "commit", "-q", "--no-verify", "-m", body, ctx=ctx)
    return git(g, "rev-parse", "HEAD").strip()


def ff_main(ctx: Ctx, expected_parent: str, sha: str) -> bool:
    """Fast-forward main to sha iff main is still at expected_parent."""
    if head(ctx) != expected_parent:
        return False
    try:
        git(ctx.root, "merge", "--ff-only", "-q", sha)
        return True
    except GitError as e:
        log(f"ff of main failed: {e}")
        return False


# ---------------------------------------------------------------- evaluation

def in_suites(ctx: Ctx, t: str) -> bool:
    return not ctx.suites or tr.suite_of(t) in ctx.suites


def sample(ctx: Ctx, n: int, seed: str) -> list[str]:
    """Known-passing sample. On a partitioned (federated) node: its own suites plus every cheap
    suite, never another node's expensive builds. Sampling the cheap suites everywhere stops one
    partition's merge from silently regressing another's (diagnosed 2026-10-12, see SKILL.md)."""
    if not ctx.suites:
        return tr.sample_ids(ctx, n, seed)
    allowed = set(ctx.suites) | set(ctx.gate["cheap_suites"])
    return tr.sample_ids(ctx, n, seed, allowed)


def gate_ids(ctx: Ctx, recs: list[dict]) -> list[str]:
    k = tr.known(ctx)
    base = read_json(ctx.state / "baseline.json", {}) or {}
    always = set(ctx.gate["always_suites"])
    ids = {t for t in k if tr.suite_of(t) in always}
    for r in recs:
        targets = r.get("targets") or r["tests"]
        # an ingested sibling candidate was verified on its own partition; run only what is ours
        ids.update(t for t in targets if not r.get("ingest") or in_suites(ctx, t))
    ids.update(sample(ctx, ctx.sample_size, base.get("commit", "seed")))
    return sorted(t for t in ids if not quarantined(ctx, t))


def evaluate(ctx: Ctx, tree: Path, ids: list[str]) -> tuple[dict, list[str]]:
    """Run ids in tree; returns (results, regressions vs known). Regressions are re-run once
    at low parallelism so a timeout under CPU load does not reject a good patch."""
    k = tr.known(ctx)
    res = tr.run_ids(ctx, tree, ids)
    # MISSING = the test no longer runs (moved to a skip list or removed): not a regression.
    regs = [t for t in ids if tr.is_pass(k.get(t)) and res.get(t, {}).get("status") not in ("PASS", "MISSING")
            and not quarantined(ctx, t)]      # a quarantined (flaky) test never rejects a candidate
    if regs:
        again = tr.run_ids(ctx, tree, regs, jobs=max(1, ctx.jobs // 2))
        res.update(again)
        regs = [t for t in regs if again.get(t, {}).get("status") not in ("PASS", "MISSING")]
    return res, regs


def gains(ctx: Ctx, res: dict, targets: list[str]) -> list[str]:
    k = tr.known(ctx)
    return [t for t in targets if tr.is_pass(res.get(t)) and not tr.is_pass(k.get(t))]


def credit_gain(ctx: Ctx, res: dict, targets: list[str]) -> float | None:
    """Rise of gate.partial_credit summed over the targets with a known value, or None when off.
    Diagnosed 2026-10-13 (swarm-decomp): 125 'partial' workers, 39% of spend, were discarded although
    103 of them were blocked only on a callee another cluster had not written yet."""
    field = ctx.gate.get("partial_credit")
    if not field:
        return None
    k = tr.known(ctx)
    total = 0.0
    for t in targets:
        before, after = (k.get(t) or {}).get(field), (res.get(t) or {}).get(field)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            total += after - before
    return total


# ---------------------------------------------------------------- outcomes

def reject(ctx: Ctx, rec: dict, reason: str) -> None:
    rec.update(status="rejected", reason=reason, t_gate=time.time())
    patch = ctx.task_dir(rec["id"]) / "patch.diff"
    body = patch.read_text(errors="surrogateescape") if patch.exists() else ""
    (ctx.rejected / f"{rec['id']}.diff").write_text(
        f"# task {rec['id']}\n# cluster {rec['signature']}\n# rejected: {reason}\n{body}", errors="surrogateescape")
    ledger_put(ctx, rec)
    log(f"REJECT {rec['id']}: {reason}")


def accept(ctx: Ctx, rec: dict, sha: str, parent: str, fixed: list[str]) -> None:
    rec.update(status="merged", merged_commit=sha, reason="", gate_fixed=fixed, t_gate=time.time())
    ledger_put(ctx, rec)
    append_jsonl(ctx.state / "merges.jsonl", {"commit": sha, "parent": parent, "task": rec["id"],
                                              "fixed": fixed, "time": time.time()})
    log(f"MERGE  {rec['id']} -> {sha[:10]} fixed {len(fixed)}: {', '.join(fixed[:4])}"
        + (f" (partial credit {rec['partial_gain']:+.3f})" if not fixed and rec.get("partial_gain") else ""))


def bump_merge_counter(ctx: Ctx, n: int) -> int:
    c = read_json(ctx.state / "counters.json", {}) or {}
    c["merges_since_full"] = c.get("merges_since_full", 0) + n
    c["merges_since_quick"] = c.get("merges_since_quick", 0) + n
    c["merges_total"] = c.get("merges_total", 0) + n
    write_json(ctx.state / "counters.json", c)
    return c["merges_since_full"]


# ---------------------------------------------------------------- gate

def recheck_clusters(ctx: Ctx, g: Path, commit: str, recs: list[dict]) -> None:
    """Re-run every known-failing member of each merged worker's cluster at the new main.
    The gate checks at most gate_targets members, so without this a fix to a shared root
    cause leaves the rest of the cluster marked FAIL and the queue keeps dispatching workers
    on tests that already pass (diagnosed 2026-10-12: ~100 workers chased ghosts)."""
    keep = frozenset(ctx.cfg["queue"]["keep_words"])
    sigs = {r.get("signature") for r in recs if not r.get("ingest")}
    k = tr.known(ctx)
    ids = [t for t, rec in k.items() if not tr.is_pass(rec) and workqueue.signature(rec, keep) in sigs
           and in_suites(ctx, t)]
    if not ids:
        return
    res = tr.run_ids(ctx, g, ids[:ctx.gate["recheck_max"]])
    tr.record(ctx, commit, res)
    log(f"recheck {len(res)} cluster members at {commit[:10]}: {sum(map(tr.is_pass, res.values()))} now pass")


def merge_batch(ctx: Ctx, recs: list[dict]) -> int:
    """Gate and merge `recs` (ledger records with status finished). Returns merged count."""
    pending: list[tuple[dict, str]] = []
    for r in recs:
        patch, _files, err = candidate_patch(ctx, r)
        if err:
            reject(ctx, r, err)
        else:
            pending.append((r, patch))
    merged = 0
    for _race in range(ctx.gate["max_main_races"]):
        if not pending:
            return merged
        main = head(ctx)
        g = prepare_gate(ctx, main)
        stacked: list[tuple[dict, str, str]] = []
        for r, patch in pending:
            sha = commit_patch(ctx, g, r, patch)
            bad = compat_check(ctx, g) if sha is not None else None
            if bad:
                git(g, "reset", "--hard", "-q", stacked[-1][2] if stacked else main)
                reject(ctx, r, f"compat check: {bad}")
            elif sha is not None:
                stacked.append((r, patch, sha))
            elif stacked:
                log(f"defer  {r['id']}: conflicts with another candidate in this batch")
            else:
                reject(ctx, r, r["reason"])
        if not stacked:
            return merged
        res, regs = evaluate(ctx, g, gate_ids(ctx, [r for r, _, _ in stacked]))
        if regs and len(stacked) > 1:
            log(f"batch of {len(stacked)} regressed {len(regs)} tests; gating one by one")
            return merged + sum(merge_batch(ctx, [r]) for r, _, _ in stacked)
        if regs:
            reject(ctx, stacked[0][0], f"regressions ({len(regs)}): {', '.join(regs[:6])}")
            return merged
        no_gain = [(r, p) for r, p, _ in stacked
                   if not r.get("ingest") and not gains(ctx, res, r.get("targets") or r["tests"])]
        credited = []
        for r, p in no_gain:      # partial credit: closer on its targets, nothing regressed
            cg = credit_gain(ctx, res, r.get("targets") or r["tests"])
            if cg is not None and cg >= ctx.gate.get("partial_min_gain", 0.05):
                r["partial_gain"] = round(cg, 4)
                credited.append((r, p))
        no_gain = [x for x in no_gain if x not in credited]
        if no_gain:
            for r, _ in no_gain:
                cg = credit_gain(ctx, res, r.get("targets") or r["tests"])
                reject(ctx, r, "no target test flipped to PASS" + (f" (credit {cg:+.3f})" if cg is not None else ""))
            pending = [(r, p) for r, p, _ in stacked if (r, p) not in no_gain]
            continue
        fixed = {}
        for r, _, _ in stacked:
            got = gains(ctx, res, r.get("targets") or r["tests"])
            if r.get("ingest"):   # the sibling's gate-verified fixes, plus anything seen flipping here
                got = sorted(set(got) | {t for t in r.get("targets") or [] if t not in res})
            fixed[r["id"]] = got
        if ctx.stamp_fixed:       # sibling: carry the verified fixes to the hub in a Fixed: trailer
            from swarmkit import federation
            new = federation.restamp(ctx, g, main, [s for _, _, s in stacked], [fixed[r["id"]] for r, _, _ in stacked])
            stacked = [(r, p, s) for (r, p, _), s in zip(stacked, new)]
        top = stacked[-1][2]
        if not ff_main(ctx, main, top):
            log("main moved during gate; re-gating on new HEAD")
            pending = [(r, p) for r, p, _ in stacked]
            continue
        tr.record(ctx, top, res)
        claimed = {t: {"status": "PASS", "reason": "", "stage": ""} for r, _, _ in stacked if r.get("ingest")
                   for t in fixed[r["id"]] if t not in res}
        if claimed:
            tr.record(ctx, top, claimed)
        parent = main
        for r, _, sha in stacked:
            accept(ctx, r, sha, parent, fixed[r["id"]])
            parent = sha
        bump_merge_counter(ctx, len(stacked))
        recheck_clusters(ctx, g, top, [r for r, _, _ in stacked])
        return merged + len(stacked)
    for r, _ in pending:
        reject(ctx, r, "main kept moving during gate")
    return merged


# ---------------------------------------------------------------- refresh / bisect

def _write_baseline(ctx: Ctx, main: str, counts: dict) -> None:
    c = read_json(ctx.state / "counters.json", {}) or {}
    write_json(ctx.state / "baseline.json", {"commit": main, "time": time.time(), "suites": counts,
                                             "suite_names": tr.list_suites(ctx, ctx.gate_tree), **tr.tree_stamp(ctx, main)})
    append_jsonl(ctx.state / "history.jsonl", {"time": time.time(), "commit": main,
                                               "merges_total": c.get("merges_total", 0), "suites": counts})
    log("baseline: " + ", ".join(f"{s} {v['pass']}/{v['total']}" for s, v in sorted(counts.items())))


def refreshing(ctx: Ctx, on: bool, what: str = "") -> None:
    """Marker for `status`: merging is paused while a refresh owns the gate tree."""
    f = ctx.state / "refreshing.json"
    if on:
        write_json(f, {"started": time.time(), "what": what})
    else:
        f.unlink(missing_ok=True)


def refresh_suites(ctx: Ctx, suites: list[str]) -> dict:
    refreshing(ctx, True, f"suites {', '.join(suites)}")
    try:
        return _refresh_suites(ctx, suites)
    finally:
        refreshing(ctx, False)


def _refresh_suites(ctx: Ctx, suites: list[str]) -> dict:
    """Baseline only these suites (new or changed on main) and fold them into known.json.
    A full refresh grows to hours on a big corpus and pauses merging; a new suite does not
    need one (diagnosed 2026-10-12: one tests/ commit set off a 1-2 h full refresh)."""
    main = head(ctx)
    g = prepare_gate(ctx, main)
    log(f"suite refresh at {main[:10]}: {', '.join(suites)}")
    event(ctx, f"baseline new/changed suites: {', '.join(suites)}", "refresh")
    res = tr.run_full(ctx, g, suites)
    k = {t: v for t, v in tr.known(ctx).items() if tr.suite_of(t) not in set(suites)}
    write_json(ctx.state / "known.json", k)
    tr.record(ctx, main, res)
    base = read_json(ctx.state / "baseline.json", {}) or {}
    counts = dict(base.get("suites") or {})
    counts.update(tr.suite_counts(res))
    # The full run's commit (seeds the gate sample) and time (bounds bisect) stay; the counts and
    # the tests-tree stamp move, so the same change does not trigger again.
    names = sorted(set(base.get("suite_names") or []) | set(suites))
    write_json(ctx.state / "baseline.json", {**base, "suites": counts, **tr.tree_stamp(ctx, main), "suite_names": names,
                                             "commit": base.get("commit", main), "time": base.get("time", time.time())})
    log("suite baseline: " + ", ".join(f"{s} {v['pass']}/{v['total']}" for s, v in sorted(tr.suite_counts(res).items())))
    return res


def refresh(ctx: Ctx, do_bisect: bool = True) -> dict:
    """Full suites at main HEAD -> new baseline. Regressions vs known are bisected and reverted."""
    refreshing(ctx, True, "full")
    try:
        return _refresh(ctx, do_bisect)
    finally:
        refreshing(ctx, False)


def _refresh(ctx: Ctx, do_bisect: bool) -> dict:
    main = head(ctx)
    g = prepare_gate(ctx, main)
    log(f"full refresh at {main[:10]}")
    event(ctx, f"full refresh at {main[:10]}", "refresh")
    res = tr.run_full(ctx, g)
    prev = tr.known(ctx)
    regs = [t for t in res if tr.is_pass(prev.get(t)) and not tr.is_pass(res[t])]
    if regs:
        again = tr.run_ids(ctx, g, regs, jobs=max(1, ctx.jobs // 2))
        res.update(again)
        regs = [t for t in regs if not tr.is_pass(again.get(t))]
    for _round in range(3):
        if not (regs and do_bisect):
            break
        log(f"refresh found {len(regs)} regressions: {', '.join(regs[:6])}")
        culprit = bisect(ctx, regs)
        if not culprit or not revert(ctx, culprit, regs):
            log("could not locate/revert culprit; accepting the regression into the baseline")
            break
        main = head(ctx)
        g = prepare_gate(ctx, main)
        lost = [t for m in read_jsonl(ctx.state / "merges.jsonl") if m["commit"] == culprit for t in m["fixed"]]
        again = tr.run_ids(ctx, g, regs + lost)   # the culprit's fixes are undone too
        res.update(again)
        regs = [t for t in regs if not tr.is_pass(again.get(t))]
    main = head(ctx)
    keep = {t: v for t, v in prev.items() if not in_suites(ctx, t)} if ctx.suites else {}
    tr.record(ctx, main, res, replace_known=True)
    if keep:          # suites outside --suites belong to other federated nodes: keep their entries
        k = tr.known(ctx)
        k.update({t: v for t, v in keep.items() if t not in k})
        write_json(ctx.state / "known.json", k)
    c = read_json(ctx.state / "counters.json", {}) or {}
    c["merges_since_full"] = 0
    c["merges_since_quick"] = 0           # the full run covered the quick suites too
    write_json(ctx.state / "counters.json", c)
    _write_baseline(ctx, main, tr.suite_counts(res))
    return res


def quick_suites(ctx: Ctx) -> list[str]:
    """Suites a quick refresh runs: --quick-suites, else gate.quick_suites, else gate.cheap_suites.
    On a partitioned (federated) node, only its own suites plus the cheap ones, like the gate sample."""
    names = ctx.quick_suites or ctx.gate["quick_suites"] or ctx.gate["cheap_suites"]
    if ctx.suites:
        allowed = set(ctx.suites) | set(ctx.gate["cheap_suites"])
        names = [s for s in names if s in allowed]
    return list(dict.fromkeys(names))


def quick_refresh(ctx: Ctx, suites: list[str] | None = None) -> dict:
    """Fast suites at main HEAD every gate.quick_every merges; regressions are bisected only over
    the merges since the previous quick or full refresh, and the culprit reverted. The gate's
    random sample misses regressions and a full refresh is too rare to revert them (diagnosed
    2026-10-12: a refresh after 200 merges found 82 regressions whose culprit sat 256 commits
    back and no longer reverted cleanly)."""
    suites = suites or quick_suites(ctx)
    refreshing(ctx, True, f"quick ({', '.join(suites)})")
    try:
        return _quick_refresh(ctx, suites)
    finally:
        refreshing(ctx, False)


def _quick_refresh(ctx: Ctx, suites: list[str]) -> dict:
    main = head(ctx)
    g = prepare_gate(ctx, main)
    last = (read_json(ctx.state / "quick.json", {}) or {}).get("time", 0)
    since = max(last, (read_json(ctx.state / "baseline.json", {}) or {}).get("time", 0))
    log(f"quick refresh at {main[:10]} ({', '.join(suites)})")
    res = tr.run_full(ctx, g, suites)
    prev = tr.known(ctx)
    regs = [t for t in res if tr.is_pass(prev.get(t)) and not tr.is_pass(res[t]) and not quarantined(ctx, t)]
    if regs:
        again = tr.run_ids(ctx, g, regs, jobs=max(1, ctx.jobs // 2))
        res.update(again)
        regs = [t for t in regs if again.get(t, {}).get("status") not in ("PASS", "MISSING")]
    found, reverted = len(regs), []
    for _round in range(3):
        if not regs:
            break
        log(f"quick refresh found {len(regs)} regressions: {', '.join(regs[:6])}")
        culprit = bisect(ctx, regs, since=since)
        if not culprit or not revert(ctx, culprit, regs):
            log("quick refresh: could not locate/revert culprit; recording the failures")
            break
        reverted.append(culprit)
        g = prepare_gate(ctx, head(ctx))
        lost = [t for m in read_jsonl(ctx.state / "merges.jsonl") if m["commit"] == culprit for t in m["fixed"]]
        again = tr.run_ids(ctx, g, regs + lost)   # the culprit's fixes are undone too
        res.update(again)
        regs = [t for t in regs if not tr.is_pass(again.get(t))]
    main = head(ctx)
    tr.record(ctx, main, res)
    npass = sum(map(tr.is_pass, res.values()))
    write_json(ctx.state / "quick.json", {"time": time.time(), "commit": main, "suites": suites, "pass": npass,
                                          "total": len(res), "found": found, "reverted": reverted,
                                          "unreverted": regs})
    c = read_json(ctx.state / "counters.json", {}) or {}
    c["merges_since_quick"] = 0
    write_json(ctx.state / "counters.json", c)
    if found:
        event(ctx, f"quick refresh: {found} regressions, {len(reverted)} reverts, {len(regs)} left", "refresh")
    log(f"quick refresh done: {npass}/{len(res)} pass; {found} regressions, {len(reverted)} reverted, "
        f"{len(regs)} left failing")
    return res


def bisect(ctx: Ctx, regs: list[str], since: float | None = None) -> str | None:
    """First swarm merge commit since `since` (default: the last full baseline) at which any of
    `regs` fails."""
    base = since if since is not None else (read_json(ctx.state / "baseline.json", {}) or {}).get("time", 0)
    reverted = {r.get("merged_commit") for r in ledger(ctx).values() if r.get("status") == "reverted"}
    commits = [m["commit"] for m in read_jsonl(ctx.state / "merges.jsonl")
               if m["time"] >= base and m["commit"] not in reverted]
    ancestors = set(git(ctx.root, "rev-list", head(ctx)).split())
    commits = [c for c in commits if c in ancestors]
    if not commits:
        return None
    log(f"bisect over {len(commits)} swarm merges since {time.strftime('%H:%M:%S', time.localtime(base))}")

    def bad(c: str) -> bool:
        g = prepare_gate(ctx, c)
        r = tr.run_ids(ctx, g, regs)
        return any(not tr.is_pass(r.get(t)) for t in regs)

    if not bad(commits[-1]):
        return None                      # the regression came from outside the swarm's commits
    lo, hi = 0, len(commits) - 1         # invariant: commits[hi] is bad
    while lo < hi:
        mid = (lo + hi) // 2
        if bad(commits[mid]):
            hi = mid
        else:
            lo = mid + 1
    log(f"bisect: culprit {commits[hi][:10]}")
    return commits[hi]


def revert(ctx: Ctx, culprit: str, regs: list[str]) -> bool:
    main = head(ctx)
    g = prepare_gate(ctx, main)
    try:
        git(g, "revert", "--no-edit", culprit, ctx=ctx)
    except GitError as e:
        git(g, "revert", "--abort", check=False)
        log(f"revert of {culprit[:10]} conflicts: {e}")
        return False
    sha = git(g, "rev-parse", "HEAD").strip()
    if not ff_main(ctx, main, sha):
        return False
    for r in ledger(ctx).values():
        if r.get("merged_commit") == culprit:
            r.update(status="reverted", reason=f"reverted by {sha[:10]}: regressed {', '.join(regs[:4])}")
            ledger_put(ctx, r)
    append_jsonl(ctx.state / "reverts.jsonl", {"culprit": culprit, "revert": sha, "regs": regs, "time": time.time()})
    log(f"REVERT {culprit[:10]} as {sha[:10]}")
    event(ctx, f"reverted {culprit[:10]} (regressed {len(regs)} tests)", "revert")
    return True


def compat_available(ctx: Ctx) -> str | None:
    """Preflight: the compat command's executable exists (else the gate would silently skip it)."""
    cmd = ctx.gate["compat_command"]
    if not cmd:
        return None
    exe = cmd[0]
    if shutil.which(exe) or (ctx.root / exe).exists() or Path(exe).exists():
        return None
    return f"gate.compat_command executable not found: {exe}"
