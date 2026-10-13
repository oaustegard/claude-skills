"""Shared plumbing: the run context, git helpers, atomic JSON state, the ledger.

Everything takes a `Ctx` instead of reading globals, so the whole swarm can be
pointed at a scratch repo (`--root`), which is what the selftest does.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from swarmkit import config as cfgmod

SKILL_DIR = Path(__file__).resolve().parents[2]
SCHEMA = Path(__file__).resolve().parent / "worker_result.schema.json"


def find_fanout() -> Path:
    """The headless `claude -p` runner from dispatching-subagents. $SWARM_FANOUT wins; then the
    sibling skill next to this one (a claude-skills clone or /mnt/skills/user); then the mount."""
    for p in (os.environ.get("SWARM_FANOUT"),
              SKILL_DIR.parent / "dispatching-subagents" / "scripts" / "headless_fanout.py",
              "/mnt/skills/user/dispatching-subagents/scripts/headless_fanout.py"):
        if p and Path(p).exists():
            return Path(p)
    return Path("/mnt/skills/user/dispatching-subagents/scripts/headless_fanout.py")


@dataclass
class Ctx:
    root: Path                                   # main checkout (owns the branch)
    cfg: dict = field(default_factory=lambda: cfgmod.load(None))
    wt_root: Path | None = None                  # one worktree per worker + _gate
    branch: str = ""                             # detected from root when empty
    jobs: int = 4                                # test parallelism for gate / baseline
    suites: list[str] = field(default_factory=list)   # [] = every suite
    sample_size: int = 150
    full_every: int = 0                          # merges between full refreshes; 0 = off
    sweep_lag: int = 100                         # every owned suite runs on main within this many merges; 0 = off
    quick_every: int = 25                        # merges between quick refreshes; 0 = off
    quick_suites: list[str] = field(default_factory=list)   # [] = gate.quick_suites, else cheap_suites
    idle_refresh: bool = True                    # full refresh when the queue drains with unrefreshed merges
    batch: int = 4
    id_prefix: str = ""                          # sibling: task ids are "<name>-wNNNNN"
    stamp_fixed: bool = False                    # sibling: add Fixed: trailers to merged commits

    def __post_init__(self) -> None:
        if self.wt_root is None:
            w = self.cfg.get("wt_root") or ""
            self.wt_root = cfgmod.resolve(self.root, w) if w else self.root.parent / f"{self.root.name}-wt"
        self.author = cfgmod.git_identity(self.root, self.cfg)

    # -- config sections
    @property
    def paths(self) -> dict:
        return self.cfg["paths"]

    @property
    def tests(self) -> dict:
        return self.cfg["tests"]

    @property
    def gate(self) -> dict:
        return self.cfg["gate"]

    @property
    def worker(self) -> dict:
        return self.cfg["worker"]

    # -- locations
    @property
    def state(self) -> Path:
        p = cfgmod.resolve(self.root, self.cfg["state_dir"])
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def rejected(self) -> Path:
        p = cfgmod.resolve(self.root, self.cfg["rejected_dir"])
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def gate_tree(self) -> Path:
        return self.wt_root / "_gate"

    @property
    def results_dir(self) -> Path:
        return self.wt_root / "_results"

    def worktree(self, task_id: str) -> Path:
        return self.wt_root / task_id

    def scratch(self, task_id: str) -> Path:
        return Path(self.worker["scratch"].format(id=task_id))

    def task_dir(self, task_id: str) -> Path:
        p = self.state / "tasks" / task_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def under(self, f: str, key: str) -> bool:
        return f.startswith(tuple(self.paths[key])) if self.paths[key] else False


# ---------------------------------------------------------------- git

class GitError(RuntimeError):
    pass


def git_env(ctx: Ctx | None) -> dict:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    if ctx is not None:
        name, email = ctx.author
        env.update(GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_NAME=name,
                   GIT_COMMITTER_EMAIL=email)
    return env


def git(cwd: Path, *args: str, check: bool = True, input: str | None = None, ctx: Ctx | None = None) -> str:
    """Run git in `cwd`; retries briefly on index.lock contention."""
    for attempt in range(20):
        # surrogateescape: diffs can carry non-UTF-8 bytes (Latin-1 sources); they must round-trip
        # through patch files and `git apply` unchanged instead of crashing the loop.
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, errors="surrogateescape",
                           input=input, env=git_env(ctx), check=False)
        if p.returncode != 0 and "index.lock" in p.stderr and attempt < 19:
            time.sleep(0.5 + attempt * 0.25)
            continue
        if check and p.returncode != 0:
            raise GitError(f"git {' '.join(args)} (in {cwd}): {p.stderr.strip()[:500]}")
        return p.stdout
    raise AssertionError("unreachable")


def head(ctx: Ctx) -> str:
    return git(ctx.root, "rev-parse", f"refs/heads/{branch(ctx)}").strip()


def branch(ctx: Ctx) -> str:
    if not ctx.branch:
        ctx.branch = git(ctx.root, "symbolic-ref", "--short", "HEAD").strip()
    return ctx.branch


def add_worktree(ctx: Ctx, path: Path, commit: str) -> None:
    """Detached worktree at `commit`; gitignored suite/tool dirs are symlinked in."""
    if path.exists():
        remove_worktree(ctx, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    git(ctx.root, "worktree", "add", "--detach", "--force", str(path), commit)
    link_untracked(ctx, path)


def link_untracked(ctx: Ctx, tree: Path) -> None:
    """Entries of the configured dirs that exist in the root but not in `tree` (downloaded
    corpora, built tools: gitignored) are symlinked, so every worktree sees the same tests."""
    for rel in ctx.tests["link_untracked"]:
        src = ctx.root / rel
        if not src.is_dir():
            continue
        for d in src.iterdir():
            dst = tree / rel / d.name
            if not dst.exists() and not dst.is_symlink():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.symlink_to(d)


def remove_worktree(ctx: Ctx, path: Path) -> None:
    git(ctx.root, "worktree", "remove", "--force", str(path), check=False)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    git(ctx.root, "worktree", "prune", check=False)


def free_gb(path: Path) -> float:
    p = path if path.exists() else path.parent
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free / 1e9


# ---------------------------------------------------------------- JSON state

def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(), strict=False)   # a worker's raw newline in a string still counts
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value) -> None:
    """Atomic write (tmp + rename) so an interrupted run never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, sort_keys=True))
    os.replace(tmp, path)


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # a torn last line after a crash
    return out


# ---------------------------------------------------------------- ledger
# state/ledger.jsonl is append-only; each line is a full snapshot of one worker's
# record and the last line per id wins.
# status: launched -> finished -> merged | rejected | failed ; merged -> reverted

def ledger(ctx: Ctx) -> dict[str, dict]:
    recs: dict[str, dict] = {}
    for r in read_jsonl(ctx.state / "ledger.jsonl"):
        recs[r["id"]] = r
    return recs


def ledger_put(ctx: Ctx, rec: dict) -> dict:
    append_jsonl(ctx.state / "ledger.jsonl", rec)
    return rec


def is_conflict(r: dict) -> bool:
    """A good fix that lost a merge race. Not a failed attempt: the next worker rebases it."""
    return r.get("status") == "rejected" and str(r.get("reason", "")).startswith(("conflict", "main kept moving"))


def attempt_epoch(ctx: Ctx) -> float:
    """Attempts launched before this time don't count toward parking or feature mode.
    Set with `swarm.py unpark` after a harness fix ($SWARM_ATTEMPT_EPOCH also works)."""
    env = float(os.environ.get("SWARM_ATTEMPT_EPOCH") or 0)
    st = (read_json(ctx.state / "epoch.json", {}) or {}).get("epoch", 0)
    return max(env, float(st))


def event(ctx: Ctx, text: str, kind: str = "harness") -> None:
    """A harness event (launch, refresh, unpark, stop, a fix to the harness) for the stats timeline."""
    append_jsonl(ctx.state / "events.jsonl", {"time": time.time(), "kind": kind, "text": text})


def quarantined(ctx: Ctx, test_id: str) -> bool:
    import fnmatch
    return any(fnmatch.fnmatchcase(test_id, g) for g in ctx.tests["quarantine"])


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)
