#!/usr/bin/env python3
"""Run a task list through parallel headless `claude -p` children.

One launch from the orchestrator runs the whole fan-out. The orchestrator does
not spend a turn per agent. Each child is a separate Claude Code process
authenticated by the host (no ANTHROPIC_API_KEY), with:

  - a fresh --session-id and --no-session-persistence. Without these a child
    inherits the parent's CLAUDE_CODE_SESSION_ID and reports the parent's id.
  - the parent's session-binding environment stripped (REMOTE_SDK_URL, ingress,
    messaging socket), so a child cannot talk to the parent's session, and
    every *TOKEN*/*SECRET*/*KEY*-named variable stripped (--keep-env to pass one).
  - --setting-sources "" and --strict-mcp-config, so no hooks, no project
    settings and no MCP servers load. The tool surface is exactly --tools.
  - --permission-mode dontAsk with an allowlist. Anything not allowed is
    refused and reported in the child's permission_denials.

    headless_fanout.py run TASKS.jsonl --work DIR [--schema S.json] [--concurrency 16]
                          [--model haiku] [--tools Read,Grep,Glob,Write] [--allow RULE ...]
                          [--retries 1] [--max-usd 5] [--timeout 900] [--dry-run]
    headless_fanout.py status DIR

TASKS.jsonl has one task per line: {"id", "prompt"} plus optional "out" (an
absolute path the child writes JSON to), "model", "tools", "allow" (extra
permission rules), "system_prompt", "json_schema" (structured output with no
file) and "timeout". This is the same {"id", "prompt", "out"} shape that
claude-workspace scripts/fanout.py dispatches over the Agent tool, so one task
file runs on either engine. `{out}` in a prompt is replaced with the out path.

A task is done only when its evidence checks out. With "out", the file must
parse as JSON and satisfy --schema. With "json_schema", structured_output must
be present. With neither, the child must finish without an error. A child's
own report of success counts for nothing. Results land in DIR/results/ID.json
(the child's final JSON). DIR/ledger.jsonl gets one line per attempt with its
cost, tokens and denials. A rerun skips tasks already done, so an interrupted
run resumes where it stopped.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import random
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

# Variables that bind a process to the parent's live session. A child that
# inherits them reports the parent's session id (measured 2026-10-11).
SESSION_ENV = (
    "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_REMOTE_SDK_URL", "CLAUDE_CODE_REMOTE_SESSION_ID",
    "SESSION_INGRESS_URL", "CLAUDE_SESSION_INGRESS_TOKEN", "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_TEE_SDK_STDOUT",
    "CLAUDE_CODE_POST_FOR_SESSION_INGRESS_V2", "CLAUDE_CODE_SYNC_SESSION_REFS",
)
# Secrets a child does not need: auth comes from the host, not these. Removed
# so that a child allowed Bash cannot print or send them. --keep-env NAME keeps one.
SECRET_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "CREDENTIAL", "PRIVATE_KEY")
TRANSIENT = ("overloaded", "rate limit", "rate_limit", "429", "529", "timed out", "ECONNRESET",
             "socket hang up", "API Error: 5")

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool,
          "integer": int, "number": (int, float), "null": type(None)}


def schema_errors(value, schema: dict, path: str = "$") -> list[str]:
    """Errors from the type/required/properties/items/enum subset of JSON Schema."""
    t = schema.get("type")
    if t:
        ok = isinstance(value, _TYPES[t]) and not (t in ("integer", "number") and isinstance(value, bool))
        if not ok:
            return [f"{path}: expected {t}, got {type(value).__name__}"]
    errs = []
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in enum")
    if isinstance(value, dict):
        errs += [f"{path}: missing {k!r}" for k in schema.get("required", []) if k not in value]
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                errs += schema_errors(value[k], sub, f"{path}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errs += schema_errors(item, schema["items"], f"{path}[{i}]")
    return errs


def check_out(out: str, schema: dict | None) -> str | None:
    """None when `out` holds valid JSON output, else the reason it does not."""
    p = Path(out)
    if not p.exists():
        return "output file missing"
    try:
        value = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return f"output not JSON: {e}"
    errs = schema_errors(value, schema) if schema else []
    return "; ".join(errs[:3]) if errs else None


def load_tasks(path: Path) -> list[dict]:
    tasks, seen = [], set()
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        t = json.loads(line)
        if not t.get("id") or not t.get("prompt"):
            sys.exit(f"{path}:{n}: task needs 'id' and 'prompt'")
        if t["id"] in seen:
            sys.exit(f"{path}:{n}: duplicate id {t['id']!r}")
        if t.get("out") and not os.path.isabs(t["out"]):
            sys.exit(f"{path}:{n}: 'out' must be absolute")
        seen.add(t["id"])
        tasks.append(t)
    return tasks


def child_env(keep: list[str] | None = None) -> dict:
    keep = set(keep or [])
    return {k: v for k, v in os.environ.items() if k not in SESSION_ENV
            and (k in keep or not any(m in k.upper() for m in SECRET_MARKERS))}


def command(t: dict, a: argparse.Namespace) -> list[str]:
    tools = t.get("tools", a.tools)
    allow = list(a.allow) + list(t.get("allow", []))
    if t.get("out"):
        # Write permission rules are spelled Edit(...). Write(path) and a bare
        # Edit are both refused under dontAsk (measured 2026-10-11). An
        # absolute path takes a leading //.
        allow.append(f"Edit(/{t['out']})")
    allow += [x for x in ("Read", "Grep", "Glob") if x in tools.split(",")]
    cmd = ["claude", "-p", "--model", t.get("model", a.model), "--output-format", "json",
           "--session-id", str(uuid.uuid4()), "--no-session-persistence",
           "--setting-sources", "", "--strict-mcp-config",
           "--tools", tools, "--permission-mode", "dontAsk"]
    if allow:
        cmd += ["--allowedTools", *allow]
    if t.get("system_prompt"):
        cmd += ["--system-prompt", t["system_prompt"]]
    if t.get("json_schema"):
        cmd += ["--json-schema", json.dumps(t["json_schema"])]
    if a.max_usd_per_task:
        cmd += ["--max-budget-usd", str(a.max_usd_per_task)]
    if a.effort:
        cmd += ["--effort", a.effort]
    return cmd


class Run:
    def __init__(self, a: argparse.Namespace, tasks: list[dict]):
        self.a, self.tasks = a, tasks
        self.work = Path(a.work).resolve()
        (self.work / "results").mkdir(parents=True, exist_ok=True)
        self.schema = json.loads(Path(a.schema).read_text()) if a.schema else None
        self.lock = threading.Lock()
        self.spent = sum(r.get("cost", 0) for r in read_ledger(self.work))
        self.stop = False

    def verdict(self, t: dict, res: dict | None) -> str | None:
        if res is None:
            return "no JSON result from child"
        if res.get("is_error"):
            return "child error: " + str(res.get("result"))[:200]
        if t.get("out"):
            return check_out(t["out"], self.schema)
        if t.get("json_schema") and res.get("structured_output") is None:
            return "no structured_output"
        return None

    def done(self, t: dict) -> bool:
        r = self.work / "results" / f"{t['id']}.json"
        if not r.exists():
            return False
        try:
            return self.verdict(t, json.loads(r.read_text())) is None
        except json.JSONDecodeError:
            return False

    def attempt(self, t: dict, n: int) -> tuple[bool, str | None]:
        prompt = t["prompt"].replace("{out}", t.get("out", ""))
        start = time.time()
        try:
            p = subprocess.run(command(t, self.a), input=prompt, capture_output=True, text=True, check=False,
                               cwd=self.a.cwd or self.work, env=child_env(self.a.keep_env),
                               timeout=t.get("timeout", self.a.timeout))
            raw, err = p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            raw, err = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout"
        try:
            res = json.loads(raw) if raw.strip() else None
        except json.JSONDecodeError:
            res = None
        reason = self.verdict(t, res)
        if res is not None:
            (self.work / "results" / f"{t['id']}.json").write_text(json.dumps(res, indent=1))
        u = (res or {}).get("usage", {})
        row = {"id": t["id"], "attempt": n, "ok": reason is None, "reason": reason,
               "cost": (res or {}).get("total_cost_usd", 0), "secs": round(time.time() - start, 1),
               "turns": (res or {}).get("num_turns"), "model": t.get("model", self.a.model),
               "in": u.get("input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0),
               "cache_read": u.get("cache_read_input_tokens", 0), "out_tok": u.get("output_tokens", 0),
               "denials": len((res or {}).get("permission_denials") or []),
               "stderr": err[-300:] if reason and err else None}
        with self.lock:
            self.spent += row["cost"]
            with (self.work / "ledger.jsonl").open("a") as f:
                f.write(json.dumps(row) + "\n")
            if self.a.max_usd and self.spent >= self.a.max_usd:
                self.stop = True
        transient = reason is not None and any(s in f"{reason} {err}" for s in TRANSIENT)
        return reason is None, ("transient" if transient else reason)

    def one(self, t: dict) -> bool:
        for n in range(1, self.a.retries + 2):
            if self.stop:
                return False
            ok, why = self.attempt(t, n)
            mark = "ok" if ok else f"FAIL ({why})"
            print(f"[{time.strftime('%H:%M:%S')}] {t['id']} attempt {n}: {mark}  spent ${self.spent:.3f}",
                  flush=True)
            if ok:
                return True
            if why == "transient":
                time.sleep(min(60, 2 ** n + random.random() * 3))
        return False

    def go(self) -> int:
        todo = [t for t in self.tasks if not self.done(t)]
        print(f"{len(self.tasks)} tasks, {len(self.tasks) - len(todo)} already done, {len(todo)} to run, "
              f"concurrency {self.a.concurrency}", flush=True)
        if self.a.dry_run:
            for t in todo[:3]:
                print(json.dumps(command(t, self.a)))
            return 0
        with cf.ThreadPoolExecutor(self.a.concurrency) as ex:
            results = list(ex.map(self.one, todo))
        failed = [t["id"] for t, ok in zip(todo, results) if not ok]
        print(f"done: {len(todo) - len(failed)}/{len(todo)} ok, spent ${self.spent:.3f}"
              + (" (stopped at --max-usd; rerun to continue)" if self.stop and failed else "")
              + (f"; failed: {failed}" if failed else ""))
        return 1 if failed else 0


def read_ledger(work: Path) -> list[dict]:
    f = work / "ledger.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []


def status(work: Path) -> int:
    rows = read_ledger(work)
    last = {}
    for r in rows:
        last[r["id"]] = r
    ok = [i for i, r in last.items() if r["ok"]]
    bad = {i: r["reason"] for i, r in last.items() if not r["ok"]}
    tok = {k: sum(r.get(k, 0) for r in rows) for k in ("in", "cache_write", "cache_read", "out_tok")}
    secs = sorted(r["secs"] for r in rows)
    print(f"{len(rows)} attempts, {len(ok)} ok, {len(bad)} failing; cost ${sum(r['cost'] for r in rows):.4f}; "
          f"tokens {tok}; denials {sum(r.get('denials', 0) for r in rows)}")
    if secs:
        print(f"child seconds: median {secs[len(secs) // 2]}, max {secs[-1]}")
    for i, why in list(bad.items())[:20]:
        print(f"  {i}: {why}")
    return 0 if not bad else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("tasks", type=Path)
    r.add_argument("--work", required=True, help="run directory: results/, ledger.jsonl")
    r.add_argument("--schema", help="JSON Schema every task's out file must satisfy")
    r.add_argument("--concurrency", type=int, default=16)
    r.add_argument("--model", default="haiku")
    r.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    r.add_argument("--tools", default="Read,Grep,Glob,Write",
                   help='built-in tools the child gets; "" for none')
    r.add_argument("--allow", nargs="*", default=[], help='extra permission rules, e.g. "Bash(git log:*)"')
    r.add_argument("--cwd", help="child working directory (default: --work; keep it outside any repo with hooks)")
    r.add_argument("--keep-env", nargs="*", default=[], help="secret-named variables to pass through")
    r.add_argument("--retries", type=int, default=1)
    r.add_argument("--timeout", type=int, default=900, help="seconds per child")
    r.add_argument("--max-usd", type=float, help="stop launching once the run has spent this much")
    r.add_argument("--max-usd-per-task", type=float)
    r.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("status")
    s.add_argument("work", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        return status(a.work)
    return Run(a, load_tasks(a.tasks)).go()


if __name__ == "__main__":
    sys.exit(main())
