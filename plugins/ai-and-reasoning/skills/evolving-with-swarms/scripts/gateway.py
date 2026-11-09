"""Metered model calls through headless `claude -p`, with a dollar cap and a quota pause.

Every call runs as a `claude -p` child with tools, MCP, skills and settings off, and
prints `stream-json`. The child's `modelUsage` is priced at list rates and appended to
`ledger.jsonl` in the run directory; once the run has spent its cap, `call` raises
BudgetExceeded. The account's five-hour usage window is read from the child's
`rate_limit_event`: calls pause until it resets once utilisation passes a per-model
threshold, and the pause is logged so the caller can leave it out of its wall clock.

No API key is needed: the host authenticates the CLI. Set EVOLVE_CLAUDE_BIN to use a
`claude` binary that is not on PATH (the desktop app's bundled CLI, a test double).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# USD per million tokens at list price (claude-api skill model table, cached 2026-10-06).
PRICES = {
    "claude-haiku-5-5": {"inp": 0.10, "out": 0.50},
    "claude-sonnet-5-5": {"inp": 2.00, "out": 10.00},
    "claude-opus-5-5": {"inp": 4.00, "out": 20.00},
}
READ_MULT, W5M_MULT, W1H_MULT = 0.10, 1.25, 2.00
HAIKU_LONG = 100_000          # Haiku 5.5 bills 5x on prompts above this many tokens
ALIASES = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}


class BudgetExceeded(RuntimeError):
    """The run has spent its dollar cap."""


class QuotaGuard(RuntimeError):
    """The account's seven-day window is too far spent to continue."""


def price(model: str, u: dict) -> float:
    """List-price dollars for one model's usage block from `modelUsage`."""
    p = PRICES[model]
    inp, out = u.get("inputTokens", 0), u.get("outputTokens", 0)
    read = u.get("cacheReadInputTokens", 0)
    w5 = u.get("cacheCreationEphemeral5mInputTokens", 0)
    w1 = u.get("cacheCreationEphemeral1hInputTokens", 0)
    rest = u.get("cacheCreationInputTokens", 0) - w5 - w1
    if rest > 0:                      # older CLIs report only the combined count
        w1 += rest
    mult = 5.0 if model == "claude-haiku-5-5" and inp + read + w5 + w1 > HAIKU_LONG else 1.0
    ip, op = p["inp"] * mult / 1e6, p["out"] * mult / 1e6
    return inp * ip + out * op + read * ip * READ_MULT + w5 * ip * W5M_MULT + w1 * ip * W1H_MULT


@dataclass
class Gateway:
    run_dir: Path
    cap: float
    max_parallel: int = 16
    quota_stop: float = 0.90        # five-hour utilisation that pauses non-Haiku calls
    quota_stop_haiku: float = 0.97  # Haiku costs ~20x less, so it may run closer to the limit
    week_stop: float = 0.45         # seven-day utilisation that ends the run
    timeout: int = 900
    spent: float = 0.0
    calls: int = 0
    last_quota: dict = field(default_factory=dict)
    pauses: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.run_dir = Path(self.run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = self.run_dir / "ledger.jsonl"
        self._lock = threading.Lock()
        self._pause_lock = threading.Lock()
        self._sem = threading.BoundedSemaphore(self.max_parallel)
        self._cwd = tempfile.mkdtemp(prefix="evolve-cc-")
        self.bin = os.environ.get("EVOLVE_CLAUDE_BIN", "claude")
        if self.ledger.exists():                       # resume: the cap holds across restarts
            for line in self.ledger.read_text().splitlines():
                self.spent += json.loads(line).get("cost", 0.0)
                self.calls += 1
        pf = self.run_dir / "pauses.jsonl"
        if pf.exists():
            for line in pf.read_text().splitlines():
                r = json.loads(line)
                self.pauses.append((r["start"], min(r["until"], time.time())))

    def call(self, model: str, system: str, user: str, *, effort: str, max_tokens: int = 32000,
             role: str = "", meta: dict | None = None, retries: int = 2) -> dict:
        """One model call. Returns the ledger record with `text`; `ok` False after retries."""
        model = ALIASES.get(model, model)
        rec: dict = {}
        for attempt in range(retries + 1):
            with self._pause_lock:
                pass                                   # wait out a pause another thread holds
            if model != "claude-haiku-5-5" and (self.last_quota.get("five_hour") or 0) >= self.quota_stop:
                self._wait_for_reset(self.last_quota)
            if self.spent >= self.cap:
                raise BudgetExceeded(f"spent {self.spent:.4f} >= cap {self.cap}")
            with self._sem:
                rec = self._run_cli(model, system, user, effort, max_tokens)
            rec.update(role=role, meta=meta or {}, attempt=attempt)
            self._record(rec)
            if rec["ok"]:
                return rec
            time.sleep(3 * (attempt + 1))
        return rec

    def _run_cli(self, model: str, system: str, user: str, effort: str, max_tokens: int) -> dict:
        sp = Path(self._cwd) / f"sys-{uuid.uuid4().hex}.txt"
        sp.write_text(system)
        # `--tools ""` must not be the last flag before the prompt, or it swallows it.
        cmd = [self.bin, "-p", "--model", model, "--no-session-persistence",
               "--output-format", "stream-json", "--verbose",
               "--tools", "", "--strict-mcp-config", "--setting-sources", "",
               "--disable-slash-commands", "--exclude-dynamic-system-prompt-sections",
               "--effort", effort, "--system-prompt-file", str(sp)]
        env = dict(os.environ, CLAUDE_CODE_EFFORT_LEVEL=effort,
                   CLAUDE_CODE_MAX_OUTPUT_TOKENS=str(max_tokens),
                   FORCE_PROMPT_CACHING_5M="1", CLAUDE_CODE_PROMPT_CACHE_TTL="5m")
        t_start = time.time()
        try:
            p = subprocess.run(cmd, input=user, capture_output=True, text=True,
                               timeout=self.timeout, cwd=self._cwd, env=env, check=False)
            out, rc, stderr = p.stdout, p.returncode, p.stderr
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            rc, stderr = -9, "timeout"
        finally:
            sp.unlink(missing_ok=True)
        result, quota = None, None
        for line in out.splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "result":
                result = d
            elif d.get("type") == "rate_limit_event":
                quota = d.get("rate_limit_info")
        rec = {"t_start": t_start, "t_end": time.time(), "model": model, "effort": effort,
               "ok": False, "text": "", "usage": {}, "cost": 0.0, "cost_cli": None, "error": None}
        if quota:
            win = quota.get("unifiedWindows") or {}
            rec["quota"] = {k: (win.get(k) or {}).get("utilization") for k in ("five_hour", "seven_day")}
            rec["quota"]["five_hour_resets"] = (win.get("five_hour") or {}).get("resetsAt")
        if result is None:
            rec["error"] = f"rc={rc} no result; stderr={stderr[-400:]}"
            return rec
        mu = result.get("modelUsage") or {}
        u = mu.get(model) or (next(iter(mu.values())) if mu else {})
        rec["usage"] = {k: u.get(k, 0) for k in (
            "inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens",
            "cacheCreationEphemeral5mInputTokens", "cacheCreationEphemeral1hInputTokens", "thinkingTokens")}
        rec["cost"] = sum(price(m, v) for m, v in mu.items() if m in PRICES)
        rec["cost_cli"] = result.get("total_cost_usd")
        if result.get("is_error") or result.get("subtype") != "success":
            rec["error"] = str(result.get("result") or result.get("subtype"))[:400]
            return rec
        rec["text"] = result.get("result") or ""
        rec["ok"] = True
        return rec

    def _record(self, rec: dict) -> None:
        with self._lock:
            self.spent += rec["cost"]
            self.calls += 1
            rec["spent_after"] = self.spent
            row = {k: v for k, v in rec.items() if k != "text"}
            row["text_len"] = len(rec.get("text") or "")
            with self.ledger.open("a") as f:
                f.write(json.dumps(row) + "\n")
            q = rec.get("quota") or {}
            if q:
                self.last_quota = q
        if q and (q.get("seven_day") or 0) >= self.week_stop:
            raise QuotaGuard(f"seven-day utilisation {q.get('seven_day')} >= {self.week_stop}")
        limit = self.quota_stop_haiku if rec["model"] == "claude-haiku-5-5" else self.quota_stop
        if q and (q.get("five_hour") or 0) >= limit:
            self._wait_for_reset(q)

    def _wait_for_reset(self, q: dict) -> None:
        """Hold every call until the five-hour window resets; log the pause."""
        with self._pause_lock:
            reset = q.get("five_hour_resets") or (time.time() + 1800)
            now = time.time()
            if now >= reset or (self.pauses and self.pauses[-1][1] >= reset):
                return
            with (self.run_dir / "pauses.jsonl").open("a") as f:
                f.write(json.dumps({"start": now, "until": reset + 30, "quota": q}) + "\n")
            time.sleep(max(0.0, reset + 30 - now))
            self.pauses.append((now, time.time()))

    def paused_before(self, t: float) -> float:
        """Seconds of quota pause before time t, to leave out of a wall clock."""
        return sum(min(e, t) - s for s, e in self.pauses if s < t)
