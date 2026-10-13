#!/usr/bin/env python3
"""Offline tests for headless_fanout.py: a fake `claude` binary stands in for the CLI.

    python3 test_headless_fanout.py

The fake reads its prompt from stdin and acts on a keyword in it: WRITE writes
valid JSON to the out path named after "OUT=", BADJSON writes junk there,
STRUCT returns structured_output, ERROR returns is_error. It also records its
argv and environment so the tests can check what a child is given.
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
RUNNER = HERE / "headless_fanout.py"

FAKE = r'''#!/usr/bin/env python3
import json, os, re, sys
prompt = sys.stdin.read()
log = os.environ["FAKE_LOG"]
with open(log, "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "env": sorted(os.environ)}) + "\n")
res = {"is_error": False, "result": "done", "total_cost_usd": 0.01, "num_turns": 1,
       "usage": {"input_tokens": 3, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0,
                 "output_tokens": 5}, "permission_denials": []}
m = re.search(r"OUT=(\S+)", prompt)
if "ERROR" in prompt:
    res.update(is_error=True, result="API Error: boom")
if "WRITE" in prompt and m:
    open(m.group(1), "w").write(json.dumps({"answer": 42}))
if "CTRLJSON" in prompt and m:
    open(m.group(1), "w").write('{"answer": 42, "notes": "line one' + chr(10) + 'line' + chr(9) + 'two"}')
if "BADJSON" in prompt and m:
    open(m.group(1), "w").write("not json")
if "STRUCT" in prompt:
    res["structured_output"] = {"answer": 1}
print(json.dumps(res))
'''


def setup(tmp: Path) -> dict:
    bindir = tmp / "bin"
    bindir.mkdir()
    fake = bindir / "claude"
    fake.write_text(FAKE)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_LOG=str(tmp / "calls.jsonl"),
               CLAUDE_CODE_SESSION_ID="parent-session", MY_API_TOKEN="s3cret", HARMLESS="1")
    return env


def run(tmp: Path, env: dict, tasks: list[dict], *extra: str) -> subprocess.CompletedProcess:
    tf = tmp / "tasks.jsonl"
    tf.write_text("".join(json.dumps(t) + "\n" for t in tasks))
    schema = tmp / "schema.json"
    schema.write_text(json.dumps({"type": "object", "required": ["answer"],
                                  "properties": {"answer": {"type": "integer"}}}))
    return subprocess.run([sys.executable, str(RUNNER), "run", str(tf), "--work", str(tmp / "run"),
                           "--schema", str(schema), "--retries", "1", *extra],
                          capture_output=True, text=True, env=env, check=False)


def calls(tmp: Path) -> list[dict]:
    return [json.loads(x) for x in (tmp / "calls.jsonl").read_text().splitlines()]


def ledger(tmp: Path) -> list[dict]:
    return [json.loads(x) for x in (tmp / "run" / "ledger.jsonl").read_text().splitlines()]


def test_out_file_verified_and_resume() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        env = setup(tmp)
        out = tmp / "o1.json"
        tasks = [{"id": "good", "prompt": "WRITE OUT={out}", "out": str(out)},
                 {"id": "junk", "prompt": "BADJSON OUT={out}", "out": str(tmp / "o2.json")},
                 {"id": "silent", "prompt": "nothing", "out": str(tmp / "o3.json")}]
        p = run(tmp, env, tasks)
        assert p.returncode == 1, p.stdout + p.stderr
        rows = ledger(tmp)
        ok = {r["id"] for r in rows if r["ok"]}
        assert ok == {"good"}, rows
        # junk and silent were each tried twice (1 retry); good once
        assert sorted(r["id"] for r in rows).count("junk") == 2
        assert any("not JSON" in (r["reason"] or "") for r in rows if r["id"] == "junk")
        assert any("missing" in (r["reason"] or "") for r in rows if r["id"] == "silent")
        n = len(calls(tmp))
        run(tmp, env, tasks)  # rerun: good is skipped
        assert all("WRITE" not in " ".join(c["argv"]) for c in calls(tmp)[n:])
        assert len(calls(tmp)) - n == 4


def test_child_flags_and_env() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        env = setup(tmp)
        out = tmp / "o.json"
        run(tmp, env, [{"id": "a", "prompt": "WRITE OUT={out}", "out": str(out)}])
        c = calls(tmp)[0]
        argv = c["argv"]
        assert "-p" in argv and "--no-session-persistence" in argv and "--strict-mcp-config" in argv
        assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
        assert argv[argv.index("--setting-sources") + 1] == ""
        assert f"Edit(/{out})" in argv, argv
        sid = argv[argv.index("--session-id") + 1]
        assert sid != "parent-session" and len(sid) == 36
        assert "CLAUDE_CODE_SESSION_ID" not in c["env"]
        assert "MY_API_TOKEN" not in c["env"] and "HARMLESS" in c["env"]


def test_deny_rules_reach_the_child() -> None:
    """A task's "deny" rules become --disallowedTools (2026-10-13 swarm-decomp: workers allowed Bash
    had to be kept off the network, where an allowlist of Bash prefixes was too narrow to work in)."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        env = setup(tmp)
        out = tmp / "o.json"
        run(tmp, env, [{"id": "a", "prompt": "WRITE OUT={out}", "out": str(out), "tools": "Read,Bash",
                        "allow": ["Bash"], "deny": ["Bash(curl:*)", "WebFetch"]}])
        argv = calls(tmp)[0]["argv"]
        i = argv.index("--disallowedTools")
        assert argv[i + 1:i + 3] == ["Bash(curl:*)", "WebFetch"], argv
        assert argv.index("--allowedTools") < i


def test_raw_control_characters_in_strings_are_accepted() -> None:
    """A model writes notes with a literal newline or tab inside a JSON string; that is still its answer
    (2026-10-13 swarm-decomp: 'output not JSON: Invalid control character' discarded a finished worker)."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        env = setup(tmp)
        out = tmp / "o.json"
        run(tmp, env, [{"id": "a", "prompt": "CTRLJSON OUT={out}", "out": str(out)}])
        raw = out.read_text()
        assert chr(10) in raw and chr(9) in raw, repr(raw)
        rows = ledger(tmp)
        assert rows and rows[-1]["ok"] is True, rows

def test_structured_output_and_errors() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        env = setup(tmp)
        schema = {"type": "object"}
        run(tmp, env, [{"id": "s", "prompt": "STRUCT", "json_schema": schema, "tools": ""},
                           {"id": "n", "prompt": "plain", "json_schema": schema, "tools": ""},
                           {"id": "e", "prompt": "ERROR"}], "--retries", "0")
        ok = {r["id"]: r["ok"] for r in ledger(tmp)}
        assert ok == {"s": True, "n": False, "e": False}, ok
        with_schema = [c["argv"] for c in calls(tmp) if "--json-schema" in c["argv"]]
        assert len(with_schema) == 2 and all(a[a.index("--tools") + 1] == "" for a in with_schema)
        st = subprocess.run([sys.executable, str(RUNNER), "status", str(tmp / "run")], capture_output=True,
                            text=True, check=False)
        assert st.returncode == 1 and "child error" in st.stdout, st.stdout


def test_budget_stops_launching() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        env = setup(tmp)
        tasks = [{"id": f"t{i}", "prompt": "STRUCT", "json_schema": {"type": "object"}} for i in range(10)]
        p = run(tmp, env, tasks, "--concurrency", "1", "--max-usd", "0.03")
        assert len(ledger(tmp)) == 3, len(ledger(tmp))
        assert "max-usd" in p.stdout


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
