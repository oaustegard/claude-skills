#!/usr/bin/env python3
"""Offline tests for evolve.py: a fake `claude` binary stands in for the CLI.

    python3 test_evolve.py

The fake answers proposer prompts with a short idea and writer prompts with a
program. The first writer call returns a program marked CHEAT, which the test's
copy of the example evaluator scores 5.0 (a scorer with a hole, like the stock
hexagon evaluator measured 2026-11-09); score_max must reject it. Later calls
return a valid arrangement. It prints stream-json with a rate_limit_event, as the
real CLI does.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVOLVE = HERE / "evolve.py"
EXAMPLE = HERE.parent / "assets" / "example"

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
prompt = sys.stdin.read()
state = os.environ["FAKE_STATE"]
n = int(open(state).read()) if os.path.exists(state) else 0
if "Propose ONE concrete change" in prompt:
    text = "Spread the points onto a staggered grid and push the outer ones to the walls."
    usage = {"inputTokens": 5, "outputTokens": 30, "cacheReadInputTokens": 900, "cacheCreationInputTokens": 800,
             "cacheCreationEphemeral5mInputTokens": 800, "cacheCreationEphemeral1hInputTokens": 0}
else:
    n += 1
    open(state, "w").write(str(n))
    if n == 1:
        body = "import numpy as np\n\ndef place_points():\n    pts = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.5, 0.25], [0.25, 0.6], [0.75, 0.6], [0.5, 0.95]])\n    return pts  # CHEAT\n"
    else:
        body = ("import numpy as np\n\ndef place_points():\n    a = 0.5176380902\n"
                "    return np.array([[0, 0], [a, 0], [1, 0.1], [0.25, 0.45], [0.75, 0.5], [0, 0.9], [0.5, 0.95], [1, 1.0]]) * 0.999\n")
    text = "Use a staggered arrangement.\n```python\n" + body + "```"
    usage = {"inputTokens": 5, "outputTokens": 900, "cacheReadInputTokens": 0, "cacheCreationInputTokens": 2500,
             "cacheCreationEphemeral5mInputTokens": 2500, "cacheCreationEphemeral1hInputTokens": 0}
model = sys.argv[sys.argv.index("--model") + 1]
assert "--effort" in sys.argv and "--system-prompt-file" in sys.argv
assert os.environ.get("FORCE_PROMPT_CACHING_5M") == "1"
print(json.dumps({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed",
      "unifiedWindows": {"five_hour": {"utilization": 0.1, "resetsAt": 0}, "seven_day": {"utilization": 0.05}}}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": text,
                  "total_cost_usd": 0.001, "modelUsage": {model: usage}}))
'''


def setup(tmp: Path) -> dict:
    bindir = tmp / "bin"
    bindir.mkdir()
    fake = bindir / "claude"
    fake.write_text(FAKE)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_STATE=str(tmp / "n"))


def evolve(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(EVOLVE), *args], capture_output=True, text=True,
                          env=env, check=False, timeout=600)


def config(tmp: Path, extra: str = "") -> Path:
    """The example config with a cheap cap and the evaluator's CHEAT hook enabled."""
    ex = tmp / "example"
    ex.mkdir()
    for f in ("problem.md", "initial_program.py"):
        (ex / f).write_text((EXAMPLE / f).read_text())
    # A scorer with a deliberate hole: any program marked CHEAT scores 5.0.
    ev = (EXAMPLE / "evaluator.py").read_text().replace(
        "        pts = [tuple", "        if 'CHEAT' in open(program_path).read():\n"
        "            return {'combined_score': 5.0}\n        pts = [tuple")
    (ex / "evaluator.py").write_text(ev)
    cfg = (EXAMPLE / "config.toml").read_text().replace("cap_usd = 0.10", "cap_usd = 0.02")
    cfg = cfg.replace("K = 4\nN = 8", "K = 2\nN = 2") + extra
    (ex / "config.toml").write_text(cfg)
    return ex / "config.toml"


def test_run_status_resume_and_bound() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        env = setup(tmp)
        cfg = config(tmp, '\n')
        run = tmp / "run"
        p = evolve(env, "run", str(cfg), "--run-dir", str(run), "--wall", "5")
        assert p.returncode == 0, p.stderr[-2000:]
        assert f"done -> {run / 'summary.json'}" in p.stdout, p.stdout
        s = json.loads((run / "summary.json").read_text())
        assert s["programs"] >= 2, s
        assert s["spent"] > 0 and s["stopped_by"] == "cap", s
        assert set(s["calls_by_role"]) >= {"proposer", "writer"}, s
        assert s["rejected_above_max"] >= 1, "the CHEAT program must be rejected by score_max"
        assert s["best_score"] <= 1.000001, s
        assert (run / "best_program.py").read_text().count("CHEAT") == 0
        led = [json.loads(x) for x in (run / "ledger.jsonl").read_text().splitlines()]
        assert all(r["quota"]["five_hour"] == 0.1 for r in led), "quota read from rate_limit_event"
        again = evolve(env, "run", str(cfg), "--run-dir", str(run))
        assert "already done" in again.stdout
        st = evolve(env, "status", str(run))
        assert json.loads(st.stdout)["programs"] == s["programs"]


def test_sandbox_prefix_is_applied() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        env = setup(tmp)
        cfg = config(tmp)
        text = cfg.read_text().replace('prefix = []', 'prefix = ["env", "EVOLVE_SANDBOX_MARK=yes"]')
        cfg.write_text(text)
        run = tmp / "run"
        p = evolve(env, "run", str(cfg), "--run-dir", str(run), "--wall", "5")
        assert p.returncode == 0, p.stderr[-2000:]
        arch = json.loads((run / "archive.json").read_text())["archive"]
        assert arch[0]["metrics"].get("sandbox_mark") == "yes", arch[0]["metrics"]


def test_missing_binary_is_reported() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = config(tmp)
        env = dict(os.environ, EVOLVE_CLAUDE_BIN="definitely-not-a-claude-binary")
        p = evolve(env, "run", str(cfg), "--run-dir", str(tmp / "run"))
        assert p.returncode == 2 and "no claude binary" in p.stderr


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
