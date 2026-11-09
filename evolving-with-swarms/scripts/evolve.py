#!/usr/bin/env python3
"""Evolve a program against an automatic scorer with swarms of cheap model calls.

    python3 evolve.py run CONFIG.toml --run-dir RUN [--seed 1] [--cap 1.0] [--wall 60]
    python3 evolve.py status RUN

One round = K swarms in parallel. A swarm is N proposer calls, each reading one parent
program and one focus x thinking-style prompt and replying with a short idea, no code;
then one writer call that reads the ideas and the parents and writes a complete
program. Each program is scored by the problem's evaluator (in a sandbox, if the config
names one) as soon as it exists, and joins the archive the next round draws parents from.

Swarm types, in slot order: refine (one of the best 2), combine (3 drawn from the best
10), explore (2 drawn from the whole archive, plus proposers that see only the problem),
fresh (the initial program; at most one per round). K=4 is one of each; larger K
cycles refine, combine, explore. N=0 runs the writer alone.

The run stops at the dollar cap or the wall clock, whichever comes first, and resumes
from RUN/archive.json when launched again. Completion line: "done -> RUN/summary.json".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prompts as P  # noqa: E402
from gateway import BudgetExceeded, Gateway, QuotaGuard  # noqa: E402

REFINE_CAP = 20          # SwarmEvolve's cap on refinement rounds per program
THRESHOLDS = (0.99, 0.999, 0.9999)

DEFAULTS = {
    "swarm": {"K": 4, "N": 8, "proposer_model": "haiku", "proposer_effort": "low",
              "writer_model": "haiku", "writer_effort": "medium", "idea_words": 45},
    "budget": {"cap_usd": 1.0, "wall_minutes": 60},
    "problem": {"score_key": "combined_score", "score_max": None, "eval_timeout": 60, "show_metrics": [],
                "eval_workers": 1},
    "sandbox": {"prefix": [], "chown_uid": None},
}


def load_config(path: Path) -> dict:
    """Read the TOML config, apply defaults, resolve file paths against its directory."""
    cfg = tomllib.loads(path.read_text())
    for sec, vals in DEFAULTS.items():
        cfg.setdefault(sec, {})
        for k, v in vals.items():
            cfg[sec].setdefault(k, v)
    pr = cfg["problem"]
    for k in ("statement", "initial_program", "evaluator"):
        if k not in pr:
            raise SystemExit(f"config [problem] needs '{k}'")
        pr[k] = str((path.parent / pr[k]).resolve())
    for k in ("entry", "interface"):
        if k not in pr:
            raise SystemExit(f"config [problem] needs '{k}'")
    return cfg


def sha(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()[:16]


def extract_code(text: str, entry: str) -> str | None:
    """The last fenced block that defines the entry function, else None."""
    for b in reversed(re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)):
        if f"def {entry}" in b:
            return b.strip() + "\n"
    if f"def {entry}" in text and "```" not in text:
        return text.strip() + "\n"
    return None


def cut_idea(text: str, words: int) -> str:
    return " ".join(text.strip().split()[:words])


class Run:
    def __init__(self, cfg: dict, run_dir: Path, seed: int, cap: float, wall_min: float) -> None:
        self.cfg, self.d, self.seed = cfg, run_dir, seed
        self.cap, self.wall = cap, wall_min * 60
        self.pr, self.sw, self.sb = cfg["problem"], cfg["swarm"], cfg["sandbox"]
        self.d.mkdir(parents=True, exist_ok=True)
        self.gw = Gateway(self.d, cap)
        self.rng = random.Random(seed)
        self.problem_text = Path(self.pr["statement"]).read_text()
        self._stage_files()
        self.archive: list[dict] = []
        self.round = 0
        used = 0.0
        st = self.d / "archive.json"
        if st.exists():
            s = json.loads(st.read_text())
            self.archive, self.round = s["archive"], s["round"]
            self.rng.setstate(_tuplify(s["rng"]))
        if (self.d / "clock.json").exists():
            used = json.loads((self.d / "clock.json").read_text())["used"]
        self.t0 = time.time() - used - self.gw.paused_before(time.time())

    # The sandbox sees only the run directory, so the evaluator and the scorer go in it.
    def _stage_files(self) -> None:
        stage = self.d / "problem"
        stage.mkdir(exist_ok=True)
        shutil.copy(self.pr["evaluator"], stage / Path(self.pr["evaluator"]).name)
        shutil.copy(HERE / "evalkit.py", stage / "evalkit.py")
        self.evaluator = stage / Path(self.pr["evaluator"]).name
        self.evalkit = stage / "evalkit.py"
        self._chown(stage)

    def _chown(self, path: Path) -> None:
        uid = self.sb.get("chown_uid")
        if uid is None:
            return
        for root, _dirs, files in os.walk(path):
            os.chown(root, uid, uid)
            for f in files:
                os.chown(os.path.join(root, f), uid, uid)

    def elapsed(self) -> float:
        return time.time() - self.t0 - self.gw.paused_before(time.time())

    def save(self) -> None:
        tmp = self.d / "archive.json.tmp"
        tmp.write_text(json.dumps({"archive": self.archive, "round": self.round, "rng": self.rng.getstate()}))
        tmp.rename(self.d / "archive.json")
        (self.d / "clock.json").write_text(json.dumps({"used": self.elapsed()}))

    def event(self, **kw: object) -> None:
        kw.setdefault("te", self.elapsed())
        kw.setdefault("spent", self.gw.spent)
        with (self.d / "events.jsonl").open("a") as f:
            f.write(json.dumps(kw) + "\n")

    def score_of(self, metrics: dict) -> float:
        """The configured metric; 0 when missing, on error, or above the sanity bound."""
        v = metrics.get(self.pr["score_key"])
        if not isinstance(v, (int, float)) or metrics.get("error"):
            return 0.0
        mx = self.pr.get("score_max")
        if mx is not None and v > mx:
            return 0.0
        return float(v)

    def evaluate(self, code: str, where: Path) -> dict:
        where.mkdir(parents=True, exist_ok=True)
        (where / "prog.py").write_text(code)
        self._chown(where)
        prefix = [x.format(run_dir=str(self.d)) for x in self.sb.get("prefix") or []]
        cmd = prefix + ["python3", str(self.evalkit), str(where), "--evaluator", str(self.evaluator),
                        "--timeout", str(self.pr["eval_timeout"]), "--workers", "1"]
        p = subprocess.run(cmd, capture_output=True, text=True, check=False,
                           timeout=self.pr["eval_timeout"] * 2 + 120)
        res = where / "results.json"
        if not res.exists():
            return {"error": f"evaluation failed rc={p.returncode}: {p.stderr[-600:]}"}
        return json.loads(res.read_text())["prog.py"]["metrics"]

    def add(self, code: str, metrics: dict, kind: str, parents: list, when: dict | None = None) -> dict:
        score = self.score_of(metrics)
        p = {"id": len(self.archive), "sha": sha(code), "code": code, "metrics": metrics, "score": score,
             "round": self.round, "kind": kind, "parents": parents, "refined": 0}
        self.archive.append(p)
        mx = self.pr.get("score_max")
        raw = metrics.get(self.pr["score_key"])
        self.event(kind="eval", sha=p["sha"], score=score, round=self.round, swarm=kind,
                   rejected_above_max=bool(mx is not None and isinstance(raw, (int, float)) and raw > mx),
                   error=str(metrics.get("error", ""))[:200] or None, **(when or {}))
        return p

    def ranked(self) -> list[dict]:
        return sorted(self.archive, key=lambda p: -p["score"])

    def plan(self) -> list[dict]:
        order = ["refine", "combine", "explore", "fresh"]
        types = [order[i] if i < 4 else order[(i - 4) % 3] for i in range(self.sw["K"])]
        ranked = self.ranked()
        eligible = [p for p in ranked if p["refined"] < REFINE_CAP]
        swarms, slot = [], 0
        for t in types:
            if t == "refine":
                pool = eligible[:2] or ranked[:1]
                swarms.append({"type": t, "parents": [pool[(self.round + slot) % len(pool)]]})
                slot += 1
            elif t == "combine":
                top = ranked[:10]
                swarms.append({"type": t, "parents": self.rng.sample(top, min(3, len(top)))})
            elif t == "explore":
                swarms.append({"type": t, "parents": self.rng.sample(self.archive, min(2, len(self.archive))),
                               "problem_only": max(1, self.sw["N"] // 4) if self.sw["N"] else 0})
            else:
                swarms.append({"type": t, "parents": [self.archive[0]]})
        return swarms

    def assignments(self, sw: dict) -> list[dict]:
        n = self.sw["N"]
        if n == 0:
            return []
        aspects = sw["type"] in ("refine", "combine")
        foci = P.ASPECTS if aspects else P.PERSPECTIVES
        phrase = "Pay particular attention to" if aspects else "Consider"
        picks = self.rng.sample(foci, n) if n <= len(foci) else [self.rng.choice(foci) for _ in range(n)]
        none_from = n - sw.get("problem_only", 0)
        return [{"parent": None if i >= none_from else sw["parents"][i % len(sw["parents"])],
                 "phrase": phrase, "focus": picks[i], "style": self.rng.choice(P.STYLES)} for i in range(n)]

    def run_swarm(self, idx: int, sw: dict, asg: list[dict]) -> dict:
        info = {"idx": idx, "type": sw["type"], "parents": [p["id"] for p in sw["parents"]]}
        show = list(self.pr.get("show_metrics") or [])

        def propose(a: dict) -> str | None:
            r = self.gw.call(self.sw["proposer_model"],
                             P.proposer_system(self.problem_text, self.pr["interface"], a["parent"], show),
                             P.proposer_user(a["phrase"], a["focus"], a["style"], self.sw["idea_words"]),
                             effort=self.sw["proposer_effort"], max_tokens=4000, role="proposer",
                             meta={"round": self.round, "swarm": idx})
            return cut_idea(r["text"], self.sw["idea_words"]) if r["ok"] and r["text"].strip() else None

        # One proposer per distinct parent goes first, so the rest read its cached prefix.
        groups: dict = {}
        for a in asg:
            groups.setdefault(id(a["parent"]), []).append(a)

        def run_group(g: list[dict]) -> list:
            first = propose(g[0])
            with ThreadPoolExecutor(max(1, len(g) - 1)) as ex:
                return [first] + list(ex.map(propose, g[1:]))

        ideas: list[str] = []
        with ThreadPoolExecutor(max(1, len(groups))) as ex:
            for res in ex.map(run_group, groups.values()):
                ideas += [t for t in res if t]
        info["ideas"] = ideas
        r = self.gw.call(self.sw["writer_model"],
                         P.writer_system(self.problem_text, self.pr["interface"], sw["parents"], show),
                         P.writer_user(ideas, len(sw["parents"]), self.pr["entry"]),
                         effort=self.sw["writer_effort"], max_tokens=32000, role="writer",
                         meta={"round": self.round, "swarm": idx})
        code = extract_code(r["text"], self.pr["entry"]) if r["ok"] else None
        if code is None:
            info["fail"] = "no code" if r["ok"] else (r.get("error") or "call failed")
            self.event(kind="nocode", round=self.round, swarm=sw["type"], error=info["fail"][:200])
            return info
        if any(p["sha"] == sha(code) for p in self.archive):
            info["dup"] = sha(code)
            self.event(kind="dup", sha=sha(code), round=self.round, swarm=sw["type"])
            return info
        info["code"] = code
        info["metrics"] = self.evaluate(code, self.d / f"r{self.round:04d}" / f"s{idx}")
        info["when"] = {"te": self.elapsed(), "spent": self.gw.spent}
        return info

    def start(self) -> None:
        if self.archive:
            return
        code = Path(self.pr["initial_program"]).read_text()
        self.add(code, self.evaluate(code, self.d / "r0000" / "s0"), "initial", [])
        self.save()

    def step(self) -> bool:
        self.round += 1
        swarms = self.plan()
        for sw in swarms:
            if sw["type"] == "refine":
                sw["parents"][0]["refined"] += 1
        asgs = [self.assignments(sw) for sw in swarms]
        go_on, infos = True, []
        with ThreadPoolExecutor(len(swarms)) as ex:
            futs = [ex.submit(self.run_swarm, i, sw, a) for i, (sw, a) in enumerate(zip(swarms, asgs))]
            for f in futs:
                try:
                    infos.append(f.result())
                except BudgetExceeded:
                    go_on = False
        for info in infos:
            if "code" in info and not any(p["sha"] == sha(info["code"]) for p in self.archive):
                info["new_id"] = self.add(info["code"], info["metrics"], info["type"], info["parents"],
                                          info.get("when"))["id"]
        with (self.d / "rounds.jsonl").open("a") as f:
            f.write(json.dumps({"round": self.round, "te": self.elapsed(), "spent": self.gw.spent,
                                "swarms": [{k: v for k, v in i.items() if k not in ("code", "when")}
                                           for i in infos]}) + "\n")
        self.save()
        return go_on

    def go(self) -> dict:
        self.start()
        stopped = "wall"
        try:
            while self.elapsed() < self.wall:
                if self.gw.spent >= self.cap or not self.step():
                    stopped = "cap"
                    break
        except QuotaGuard as e:
            stopped = f"quota: {e}"
        best = self.ranked()[0]
        (self.d / "best_program.py").write_text(best["code"])
        summary = summarize(self.d)
        summary.update(seed=self.seed, cap=self.cap, rounds=self.round, stopped_by=stopped,
                       config={k: self.cfg[k] for k in ("swarm",)})
        (self.d / "summary.json").write_text(json.dumps(summary, indent=1))
        print(f"done -> {self.d / 'summary.json'}", flush=True)
        return summary


def summarize(run_dir: Path) -> dict:
    """Spend, best score and dollars to each threshold, from the run's ledger and events."""
    ev = [json.loads(x) for x in (run_dir / "events.jsonl").read_text().splitlines()] \
        if (run_dir / "events.jsonl").exists() else []
    led = [json.loads(x) for x in (run_dir / "ledger.jsonl").read_text().splitlines()] \
        if (run_dir / "ledger.jsonl").exists() else []
    evals = [e for e in ev if e.get("kind") == "eval"]
    best = max((e["score"] for e in evals), default=None)
    to = {}
    for t in THRESHOLDS:
        hits = [e["spent"] for e in evals if e["score"] >= t]
        to[str(t)] = round(min(hits), 4) if hits else None
    by_role: dict = {}
    for r in led:
        b = by_role.setdefault(r.get("role") or "?", {"calls": 0, "cost": 0.0, "failed": 0})
        b["calls"] += 1
        b["cost"] = round(b["cost"] + r.get("cost", 0.0), 6)
        b["failed"] += 0 if r.get("ok") else 1
    last_q = next((r["quota"] for r in reversed(led) if r.get("quota")), None)
    return {"programs": len(evals), "best_score": best, "spent": round(sum(r.get("cost", 0) for r in led), 4),
            "usd_to": to, "calls_by_role": by_role, "rejected_above_max": sum(1 for e in evals if e.get("rejected_above_max")),
            "duplicates": sum(1 for e in ev if e.get("kind") == "dup"),
            "no_code": sum(1 for e in ev if e.get("kind") == "nocode"), "last_quota": last_q}


def _tuplify(x: object) -> object:
    return tuple(_tuplify(i) for i in x) if isinstance(x, list) else x


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("config", type=Path)
    r.add_argument("--run-dir", type=Path, required=True)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--cap", type=float, help="dollar cap (default: [budget] cap_usd)")
    r.add_argument("--wall", type=float, help="minutes of run time (default: [budget] wall_minutes)")
    s = sub.add_parser("status")
    s.add_argument("run_dir", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(summarize(a.run_dir), indent=1))
        return 0
    cfg = load_config(a.config)
    if (a.run_dir / "summary.json").exists():
        print(f"already done -> {a.run_dir / 'summary.json'}")
        return 0
    if shutil.which(os.environ.get("EVOLVE_CLAUDE_BIN", "claude")) is None:
        print("no claude binary on PATH: install Claude Code or set EVOLVE_CLAUDE_BIN", file=sys.stderr)
        return 2
    Run(cfg, a.run_dir, a.seed, a.cap if a.cap is not None else cfg["budget"]["cap_usd"],
        a.wall if a.wall is not None else cfg["budget"]["wall_minutes"]).go()
    return 0


if __name__ == "__main__":
    sys.exit(main())
