"""Run statistics: metrics.json, report.md and (with matplotlib) four charts.

    swarm.py stats [--out DIR] [--ledger EXTRA.jsonl ...] [--event "HH:MM text" ...]

Charts: (1) cumulative merges on main over time with harness events drawn as
vertical lines, (2) outcomes by worker kind (normal / high effort / feature /
rebase / ingested), (3) cumulative spend, (4) pass count per suite over time.

The event-annotation pattern: every harness change gets a timestamped line in
state/events.jsonl (the loop writes launches, refreshes, unparks, reverts and
stops itself; add your own with `swarm.py event "conflicts become rebase tasks"`).
A merge-rate curve without them cannot be read: the inflection points ARE the
harness fixes. --ledger adds sibling ledgers collected at stand-down; their
records count under their own id prefix. Every number carries `as_of`.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from pathlib import Path

from swarmkit.common import Ctx, read_jsonl, write_json


def kind(r: dict) -> str:
    if r.get("ingest"):
        return f"ingested ({r.get('sibling') or 'peer'})"
    if r.get("rebase_of"):
        return "rebase"
    if r.get("feature"):
        return "feature"
    if r.get("effort") == "high":
        return "high effort"
    return "normal"


def collect(ctx: Ctx, extra: list[str]) -> dict[str, dict]:
    recs: dict[str, dict] = {}
    for path in [ctx.state / "ledger.jsonl", *map(Path, extra)]:
        for r in read_jsonl(path):
            recs[r["id"]] = r
    return recs


def metrics(ctx: Ctx, recs: dict[str, dict]) -> dict:
    by_kind: dict = defaultdict(Counter)
    for r in recs.values():
        by_kind[kind(r)][r["status"]] += 1
    workers = [r for r in recs.values() if not r.get("ingest")]
    spend = sum(r.get("cost_usd") or 0 for r in workers)
    merged = [r for r in recs.values() if r["status"] == "merged"]
    return {"as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "workers": len(workers),
            "status": dict(Counter(r["status"] for r in recs.values())), "spend_usd": round(spend, 3),
            "usd_per_merge": round(spend / len(merged), 4) if merged else None,
            "by_kind": {k: dict(v) for k, v in by_kind.items()},
            "merges_on_main": len(read_jsonl(ctx.state / "merges.jsonl")),
            "reverts": len(read_jsonl(ctx.state / "reverts.jsonl"))}


def report(m: dict, events: list[dict]) -> str:
    lines = [f"# Swarm run statistics (as of {m['as_of']})", "",
             (f"workers {m['workers']}, spend ${m['spend_usd']:.2f}, merges on main {m['merges_on_main']}, "
              f"${m['usd_per_merge']} per merge, reverts {m['reverts']}"), "",
             "| worker kind | merged | rejected | failed | reverted | launched | finished |",
             "|---|" + "---|" * 6]
    for k, c in sorted(m["by_kind"].items()):
        lines.append(f"| {k} | " + " | ".join(str(c.get(s, 0)) for s in
                                              ("merged", "rejected", "failed", "reverted", "launched", "finished")) + " |")
    lines += ["", "## Harness events", ""]
    lines += [f"- {time.strftime('%H:%M', time.localtime(e['time']))} [{e['kind']}] {e['text']}" for e in events]
    return "\n".join(lines) + "\n"


def charts(ctx: Ctx, out: Path, recs: dict, events: list[dict]) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    t0 = min([r.get("t_launch") or time.time() for r in recs.values()] + [time.time()])
    h = lambda t: (t - t0) / 3600
    merges = sorted(m["time"] for m in read_jsonl(ctx.state / "merges.jsonl"))
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.step([h(t) for t in merges], range(1, len(merges) + 1), where="post", color="#3a6ea5")
    marks = [e for e in events if e["kind"] not in ("loop",)]
    for i, e in enumerate(marks):
        ax.axvline(h(e["time"]), color="#999", lw=0.8, ls="--")
        ax.text(h(e["time"]), (len(merges) or 1) * (0.95 - 0.07 * (i % 6)), " " + e["text"][:40], fontsize=7)
    ax.set(xlabel="hours since first launch", ylabel="cumulative merges on main", title="Merges with harness events")
    fig.tight_layout()
    fig.savefig(out / "merges_timeline.png", dpi=130)
    plt.close(fig)
    kinds = Counter()
    for r in recs.values():
        kinds[(kind(r), r["status"])] += 1
    ks = sorted({k for k, _ in kinds})
    sts = ["merged", "rejected", "failed", "reverted"]
    fig, ax = plt.subplots(figsize=(9, 4))
    bottom = [0] * len(ks)
    for s in sts:
        vals = [kinds[(k, s)] for k in ks]
        ax.bar(ks, vals, bottom=bottom, label=s)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.legend()
    ax.set(title="Outcomes by worker kind", ylabel="workers")
    fig.tight_layout()
    fig.savefig(out / "outcomes_by_kind.png", dpi=130)
    plt.close(fig)
    done = sorted((r.get("t_done") or r.get("t_launch") or t0, r.get("cost_usd") or 0)
                  for r in recs.values() if not r.get("ingest"))
    acc, xs, ys = 0.0, [], []
    for t, c in done:
        acc += c
        xs.append(h(t))
        ys.append(acc)
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(xs, ys, color="#a5523a")
    ax.set(xlabel="hours", ylabel="USD", title="Cumulative worker spend")
    fig.tight_layout()
    fig.savefig(out / "spend.png", dpi=130)
    plt.close(fig)
    hist = read_jsonl(ctx.state / "history.jsonl")
    if hist:
        fig, ax = plt.subplots(figsize=(9, 4))
        for s in sorted({s for x in hist for s in x["suites"]}):
            pts = [(h(x["time"]), x["suites"][s]["pass"]) for x in hist if s in x["suites"]]
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=3, label=s)
        ax.legend(fontsize=7, ncol=2)
        ax.set(xlabel="hours", ylabel="passing tests", title="Pass count per suite at each baseline")
        fig.tight_layout()
        fig.savefig(out / "suites.png", dpi=130)
        plt.close(fig)
    return True


def main(ctx: Ctx, out: Path, extra: list[str]) -> int:
    out.mkdir(parents=True, exist_ok=True)
    recs = collect(ctx, extra)
    events = read_jsonl(ctx.state / "events.jsonl")
    m = metrics(ctx, recs)
    write_json(out / "metrics.json", m)
    (out / "report.md").write_text(report(m, events))
    drew = charts(ctx, out, recs, events)
    print(f"wrote {out}/metrics.json, report.md" + (", 4 charts" if drew else
          " (no matplotlib: charts skipped; run with an interpreter that has it)"))
    return 0
