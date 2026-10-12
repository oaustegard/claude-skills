"""Per-project swarm configuration: one TOML (or JSON) file, every knob in one place.

The harness names no project. Everything that differs between projects (how
tests run, which paths a worker may change, how suites rank, the worker prompt,
the model) comes from this file. `references/config.md` documents each key;
`assets/swarm.example.toml` is a filled-in starting point.

Paths in the file are relative to the project root unless absolute.
"""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11: JSON configs still work
    tomllib = None

FEATURE_MODE = """FEATURE MODE. Earlier workers on this cluster stopped because the fix needs a whole missing
feature (see their notes), not a local patch. Your mandate overrides the "minimal fix" and budget rules:
implement that feature end to end, across every module it touches, in the project's style, with new
modules where a file would grow too large. Plan first: list the pieces in {scratch}/plan.md, then build
them in order, running the representative tests after each piece. You have up to ~150 tool calls and
about an hour. A coherent subset that makes at least one representative test PASS with no regressions is
a success (status fixed); say in notes what is left. Never make an unsupported construct silently
produce wrong output: unsupported parts must still fail loudly."""

DEFAULTS: dict = {
    "project": "project",
    "state_dir": ".swarm/state",          # ledger, known.json, baseline, per-task dirs
    "rejected_dir": ".swarm/rejected",    # rejected diffs with the reason
    "wt_root": "",                        # "" = <root>-wt next to the checkout
    "tests": {
        # argv; {suites} comma list, {jobs}, {out} JSON path, {tree} checkout under test
        "command": ["python3", "tests/run.py", "--suite", "{suites}", "--jobs", "{jobs}",
                    "--json", "{out}", "--quiet"],
        "filter_args": ["--filter", "{glob}"],   # appended once per test id
        "filter_escape": "fnmatch",             # "fnmatch": wrap * ? [ ] as [c]; "none"
        "env": {},                              # values may use {tree} and $VARS
        "timeout": 3600,                        # seconds per invocation
        "suites_dir": "tests/suites",           # every subdirectory is a suite
        "suites": [],                           # explicit suite list instead of listing suites_dir
        "tests_tree": "tests",                  # a change to this tree on main triggers a refresh
        "link_untracked": ["tests/suites", "tests/tools"],  # gitignored entries symlinked into worktrees
        "source_root": "tests/suites",          # <source_root>/<suite>/<rel>: sizes rank representatives
        "quarantine": [],                       # globs: flaky tests, never gated as regressions nor queued
    },
    "paths": {
        "code": ["src/"],          # a candidate must change something here; must apply cleanly
        "allowed": [],             # also taken, best effort: dropped on conflict (docs, notes)
        "forbidden": ["tests/"],   # any edit here rejects the candidate (the worker gamed the tests)
        "junk": ["__pycache__/", ".pyc"],
    },
    "queue": {
        "ladder": [["smoke", 6]],  # [suite-name prefix, level]; first match wins; higher runs first
        "default_level": 2,
        "keep_words": [],          # quoted words kept verbatim in signatures (language keywords)
        "shard_size": 10,
        "max_shards": 6,
        "max_test_attempts": 3,    # a test tried this often without a merge is parked
        "reps": 3,                 # representative tests per work item
        "gate_targets": 20,        # cluster members the gate checks for a flip
        "feature_after": 2,        # failed attempts on a signature before feature mode
    },
    "gate": {
        "always_suites": ["smoke"],   # every known test in these runs at every gate
        "cheap_suites": ["smoke"],    # sampled on every federated node (cross-partition guard)
        "compat_command": [],         # argv run in the gate tree per candidate; {tree}; non-zero rejects
        "batch": 4,
        "sample": 150,
        "full_every": 200,            # merges between full refreshes
        "quick_every": 25,            # merges between quick refreshes of quick_suites; 0 = off
        "quick_suites": [],           # [] = cheap_suites; fast suites run and bisected every quick_every
        "idle_refresh": True,         # full refresh when the queue drains with merges since the last one
        "recheck_max": 1500,          # cluster members re-run after each merge
        "max_main_races": 3,
        "coauthor": "Claude Haiku 5.5 <noreply@anthropic.com>",
    },
    "git": {"author_name": "", "author_email": ""},   # "" = git config of the root checkout
    "worker": {
        "system_prompt": "",          # path; required for real runs
        "schema": "",                 # "" = the bundled worker_result.schema.json
        "model": "haiku",
        "effort": "",                 # first attempt; later attempts and feature work use "high"
        "timeout": 1500,
        "per_task_usd": 2.0,
        "feature_timeout": 3600,
        "feature_usd": 5.0,
        "tools": "Read,Grep,Glob,Edit,Write,Bash",
        "allow": ["Edit(//tmp/**)", "Bash"],      # plus Edit(/<worktree>/**), always
        "scratch": "/tmp/{id}",                   # deleted when the worker is reaped
        "repro_command": "",                      # per representative: {suite} {test}
        "task_footer": "Follow the procedure in your instructions.",
        "feature_mode": FEATURE_MODE,
        "preflight_files": [],                    # must exist in the root before launch
    },
    "run": {
        "concurrency": 24,
        "max_load": 0.0,         # 0 = 3 x CPUs
        "min_free_gb": 3.0,      # no launches below this much free disk on wt_root
        "idle_max": 14400,       # seconds to wait on an empty queue for new tests/ commits
        "poll": 5.0,
    },
    "federation": {
        "remote": "",            # git URL or path of the transport repo
        "prefix": "swarm/",      # branches <prefix>main, <prefix>state, <prefix>cand/<NAME>
        "poll": 180,
        "rebase_every": 900,
        "setup_command": [],     # run by sibling_setup.sh in a new container
    },
    "compare": {
        "arms": {
            "haiku": {"model": "haiku", "effort": ""},
            "haiku-high": {"model": "haiku", "effort": "high"},
            "sonnet": {"model": "sonnet", "effort": "medium"},
        },
        "usd_cap": 3.0,
        "sample": 120,
    },
}


def _merge(base: dict, over: dict, path: str = "") -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if k not in base:
            raise ValueError(f"unknown config key {path}{k}")
        if isinstance(base[k], dict) and k not in ("arms", "env"):
            if not isinstance(v, dict):
                raise ValueError(f"config key {path}{k} must be a table")
            out[k] = _merge(base[k], v, f"{path}{k}.")
        else:
            out[k] = v
    return out


def load(path: Path | None) -> dict:
    """DEFAULTS overlaid with the file at `path` (TOML or JSON). Unknown keys are an error,
    so a typo fails at launch instead of silently running on a default."""
    if path is None or not path.exists():
        if path is not None:
            raise FileNotFoundError(f"config not found: {path}")
        return copy.deepcopy(DEFAULTS)
    text = path.read_text()
    if path.suffix == ".json":
        data = json.loads(text)
    else:
        if tomllib is None:
            raise RuntimeError("TOML config needs Python 3.11+; use a .json config")
        data = tomllib.loads(text)
    return _merge(DEFAULTS, data)


def resolve(root: Path, p: str) -> Path:
    q = Path(p).expanduser()
    return q if q.is_absolute() else root / q


def git_identity(root: Path, cfg: dict) -> tuple[str, str]:
    name, email = cfg["git"]["author_name"], cfg["git"]["author_email"]
    if not name:
        name = subprocess.run(["git", "config", "user.name"], cwd=root, capture_output=True,
                              text=True, check=False).stdout.strip() or "swarm"
    if not email:
        email = subprocess.run(["git", "config", "user.email"], cwd=root, capture_output=True,
                               text=True, check=False).stdout.strip() or "swarm@localhost"
    return name, email
