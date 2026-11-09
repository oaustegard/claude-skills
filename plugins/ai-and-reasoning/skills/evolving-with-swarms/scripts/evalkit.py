"""Score every program in a directory with the problem's evaluator, one process group each.

    python3 evalkit.py PROG_DIR --evaluator EVAL.py [--timeout 60] [--workers 4]

The evaluator module must define `evaluate(program_path) -> dict` of numbers and
strings. Each program is scored in its own Python process group, killed at the
timeout, so a runaway program cannot outlive its slot. Writes PROG_DIR/results.json:
{filename: {"metrics": {...}, "t": end_time, "dt": seconds}}.

Run this under a sandbox prefix (see SKILL.md, Sandboxing) when the programs are
model-written: the evaluator imports and executes them.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ONE = ("import json, sys, importlib.util; "
       "spec = importlib.util.spec_from_file_location('evaluator', sys.argv[1]); "
       "ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev); "
       "m = ev.evaluate(sys.argv[2]); "
       "print('@@RESULT@@' + json.dumps({k: v for k, v in m.items() if isinstance(v, (int, float, str))}))")


def score(path: Path, evaluator: Path, timeout: float) -> dict:
    """Run the evaluator on one program; never raises, records failures as metrics.error."""
    t0 = time.time()
    p = subprocess.Popen([sys.executable, "-c", ONE, str(evaluator), str(path)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         start_new_session=True, cwd=str(path.parent))
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return {"metrics": {"error": f"Timeout after {timeout}s"}, "t": time.time(), "dt": time.time() - t0}
    for line in out.splitlines():
        if line.startswith("@@RESULT@@"):
            return {"metrics": json.loads(line[len("@@RESULT@@"):]), "t": time.time(), "dt": time.time() - t0}
    return {"metrics": {"error": ("no result: " + err[-600:]).strip()}, "t": time.time(), "dt": time.time() - t0}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prog_dir", type=Path)
    ap.add_argument("--evaluator", type=Path, required=True)
    ap.add_argument("--timeout", type=float, default=60)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    progs = sorted(a.prog_dir.glob("*.py"))
    with ThreadPoolExecutor(a.workers) as ex:
        res = dict(zip((p.name for p in progs), ex.map(lambda p: score(p, a.evaluator.resolve(), a.timeout), progs)))
    tmp = a.prog_dir / "results.json.tmp"
    tmp.write_text(json.dumps(res, indent=1))
    tmp.rename(a.prog_dir / "results.json")


if __name__ == "__main__":
    main()
