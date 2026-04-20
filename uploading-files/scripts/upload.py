#!/usr/bin/env python3
"""File-upload bridge for Claude Code on the Web.

CCotw has no native file mount. This script uses a throwaway GitHub branch
on the working repo's `origin` remote as an upload target:

    init     create the upload branch on origin and print the GitHub web
             upload URL for the user to drop files into
    fetch    download files committed onto the branch into ./.uploads/
    cleanup  delete the remote upload branch
    status   show the branch name, URL, and whether it exists on origin

Branch name: upload-<short-session-id>. Session id comes from
$CLAUDE_SESSION_ID, then from the most recent transcript under
~/.claude/projects/<encoded-cwd>/, then from a UTC timestamp as fallback.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UPLOADS_DIR = ".uploads"


def _token() -> str:
    for var in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_PAT", "GH_PAT"):
        val = os.environ.get(var)
        if val:
            return val
    sys.exit("error: no GitHub token in env (GH_TOKEN/GITHUB_TOKEN/GITHUB_PAT/GH_PAT)")


def _api(method: str, path: str, body: dict | None = None) -> Any:
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {_token()}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} -> {e.code}: {msg}") from e


def _origin_repo() -> tuple[str, str]:
    """Return (owner, repo) parsed from `git remote get-url origin`.

    Supports github.com SSH/HTTPS URLs and the CCotw local-proxy form
    (``http://local_proxy@127.0.0.1:PORT/git/<owner>/<repo>``).
    """
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: not in a git repo or origin missing: {e.stderr.strip()}")
    path: str | None = None
    if url.startswith("git@github.com:"):
        path = url.split(":", 1)[1]
    elif "github.com/" in url:
        path = url.split("github.com/", 1)[1]
    elif "/git/" in url:  # CCotw local proxy
        path = url.split("/git/", 1)[1]
    if path is None:
        sys.exit(f"error: cannot parse a github owner/repo from origin url: {url}")
    if path.endswith(".git"):
        path = path[:-4]
    owner, _, repo = path.partition("/")
    repo = repo.split("/", 1)[0]  # tolerate trailing path segments
    if not owner or not repo:
        sys.exit(f"error: could not parse owner/repo from origin url: {url}")
    return owner, repo


def _session_id() -> str:
    for var in (
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDE_CODE_REMOTE_SESSION_ID",
        "CLAUDE_SESSION_ID",
    ):
        sid = os.environ.get(var)
        if sid:
            return sid
    projects = Path.home() / ".claude" / "projects"
    if projects.is_dir():
        encoded = "-" + str(Path.cwd().resolve()).replace("/", "-")
        proj = projects / encoded
        if proj.is_dir():
            jsonls = sorted(proj.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
            if jsonls:
                return jsonls[-1].stem
    return "ts" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _branch_name() -> str:
    """upload-<short> where <short> is the last 12 alnum chars of the session id."""
    sid = _session_id()
    alnum = "".join(c for c in sid if c.isalnum())
    short = alnum[-12:] if len(alnum) >= 4 else (alnum or "session")
    return f"upload-{short}"


def _branch_exists(owner: str, repo: str, branch: str) -> bool:
    try:
        _api("GET", f"/repos/{owner}/{repo}/branches/{branch}")
        return True
    except RuntimeError as e:
        if " -> 404" in str(e):
            return False
        raise


def _default_branch(owner: str, repo: str) -> str:
    return _api("GET", f"/repos/{owner}/{repo}")["default_branch"]


def _upload_url(owner: str, repo: str, branch: str) -> str:
    return f"https://github.com/{owner}/{repo}/upload/{branch}"


def _ensure_gitignore(entry: str) -> None:
    gi = Path.cwd() / ".gitignore"
    needle = entry.rstrip("/")
    if gi.exists():
        for line in gi.read_text().splitlines():
            if line.strip().rstrip("/") == needle:
                return
        text = gi.read_text()
        if text and not text.endswith("\n"):
            text += "\n"
        gi.write_text(text + entry + "\n")
    else:
        gi.write_text(entry + "\n")


def cmd_init() -> int:
    owner, repo = _origin_repo()
    branch = _branch_name()
    if _branch_exists(owner, repo, branch):
        print(f"Branch {branch} already exists on {owner}/{repo}; reusing it.")
    else:
        default = _default_branch(owner, repo)
        ref = _api("GET", f"/repos/{owner}/{repo}/git/ref/heads/{default}")
        sha = ref["object"]["sha"]
        _api(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": sha},
        )
        print(f"Created branch {branch} on {owner}/{repo} (from {default}).")
    print()
    print("UPLOAD URL — share verbatim with the user:")
    print(f"  {_upload_url(owner, repo, branch)}")
    print()
    print("Tell the user to drop files on that page and click 'Commit changes'.")
    print("When they confirm, run:  upload.py fetch")
    return 0


def cmd_fetch() -> int:
    owner, repo = _origin_repo()
    branch = _branch_name()
    if not _branch_exists(owner, repo, branch):
        print(f"error: branch {branch} not found on {owner}/{repo}; run init first.")
        return 1
    default = _default_branch(owner, repo)
    cmp_data = _api("GET", f"/repos/{owner}/{repo}/compare/{default}...{branch}")
    files = [f for f in cmp_data.get("files", []) if f.get("status") != "removed"]
    if not files:
        print(f"No files on {branch} yet.")
        print(f"Upload URL: {_upload_url(owner, repo, branch)}")
        return 0
    out_dir = Path.cwd() / UPLOADS_DIR
    out_dir.mkdir(exist_ok=True)
    _ensure_gitignore(UPLOADS_DIR + "/")
    fetched: list[tuple[Path, int]] = []
    for f in files:
        rel = f["filename"]
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{rel}"
        req = urllib.request.Request(raw_url)
        req.add_header("Authorization", f"token {_token()}")
        with urllib.request.urlopen(req) as r:
            data = r.read()
        dest = out_dir / Path(rel).name
        dest.write_bytes(data)
        fetched.append((dest, len(data)))
    print(f"Fetched {len(fetched)} file(s) into {out_dir}:")
    for dest, size in fetched:
        print(f"  {dest.relative_to(Path.cwd())}  ({size} bytes)")
    print()
    print("When done with these files, clean up the remote branch:")
    print("  upload.py cleanup")
    return 0


def cmd_cleanup() -> int:
    owner, repo = _origin_repo()
    branch = _branch_name()
    if not _branch_exists(owner, repo, branch):
        print(f"Branch {branch} already gone on {owner}/{repo}.")
        return 0
    _api("DELETE", f"/repos/{owner}/{repo}/git/refs/heads/{branch}")
    print(f"Deleted remote branch {branch} on {owner}/{repo}.")
    print(f"Local files in ./{UPLOADS_DIR}/ are kept (gitignored).")
    return 0


def cmd_status() -> int:
    owner, repo = _origin_repo()
    branch = _branch_name()
    exists = _branch_exists(owner, repo, branch)
    print(f"repo:    {owner}/{repo}")
    print(f"branch:  {branch}")
    print(f"exists:  {exists}")
    print(f"url:     {_upload_url(owner, repo, branch)}")
    return 0


COMMANDS = {
    "init": cmd_init,
    "fetch": cmd_fetch,
    "cleanup": cmd_cleanup,
    "status": cmd_status,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f"usage: upload.py {{{'|'.join(COMMANDS)}}}")
    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main())
