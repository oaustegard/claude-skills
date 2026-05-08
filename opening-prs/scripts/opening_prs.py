"""
opening_prs — open a GitHub PR via API as a flowing graph.

The "NEVER push directly to main" rule is `validate=`; the
"poll mergeable_state until settled" prose is `retry_until=`.

See SKILL.md for the full picture.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from typing import Iterable, List, Tuple

# The flowing skill is the canonical source. Try the package layout first,
# fall back to the bare module name (legacy materialized layout).
try:
    from flowing import task, Flow, StepState  # type: ignore
except ImportError:  # pragma: no cover — defensive only
    import importlib.util as _ilu
    import sys as _sys
    _SKILL = "/mnt/skills/user/flowing/scripts/flowing.py"
    if not os.path.exists(_SKILL):
        raise ImportError(
            "opening_prs requires the flowing skill at "
            f"{_SKILL} or `from flowing import ...` on the python path"
        )
    _spec = _ilu.spec_from_file_location("flowing", _SKILL)
    _flow = _ilu.module_from_spec(_spec)
    _sys.modules["flowing"] = _flow
    _spec.loader.exec_module(_flow)
    task, Flow, StepState = _flow.task, _flow.Flow, _flow.StepState


# ── GitHub helpers ─────────────────────────────────────────────────

GITHUB_USER_AGENT = "opening-prs"


def _gh_token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _gh_api(method: str, endpoint: str, data: dict | None = None) -> dict:
    token = _gh_token()
    if not token:
        raise RuntimeError(
            "GH_TOKEN (or GITHUB_TOKEN) not set — opening-prs needs an "
            "authenticated PAT. See SKILL.md > Auth."
        )
    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "User-Agent": GITHUB_USER_AGENT,
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
    })
    return json.loads(urllib.request.urlopen(req).read())


SETTLED_MERGEABLE_STATES = frozenset({"clean", "dirty", "unstable", "behind", "blocked"})


def _get_branch_head(repo: str, branch: str) -> str:
    ref = _gh_api("GET", f"/repos/{repo}/git/refs/heads/{branch}")
    return ref["object"]["sha"]


def _create_branch(repo: str, branch: str, from_sha: str) -> dict:
    return _gh_api(
        "POST", f"/repos/{repo}/git/refs",
        {"ref": f"refs/heads/{branch}", "sha": from_sha},
    )


def _put_file(repo: str, branch: str, path: str, content: str,
              message: str | None = None) -> dict:
    payload = {
        "message": message or f"Add {path}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    try:
        existing = _gh_api(
            "GET", f"/repos/{repo}/contents/{path}?ref={branch}"
        )
        if isinstance(existing, dict) and existing.get("sha"):
            payload["sha"] = existing["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    return _gh_api("PUT", f"/repos/{repo}/contents/{path}", payload)


def _create_pull_request(repo: str, head: str, base: str,
                          title: str, body: str) -> dict:
    return _gh_api(
        "POST", f"/repos/{repo}/pulls",
        {"title": title, "body": body, "head": head, "base": base},
    )


def _get_pull_request(repo: str, number: int) -> dict:
    return _gh_api("GET", f"/repos/{repo}/pulls/{number}")


# ── Edge contracts ─────────────────────────────────────────────────

PROTECTED_BRANCH_NAMES = frozenset({"main", "master", "trunk", "production", "prod"})


def _must_not_be_base_branch_factory(base: str):
    base_norm = base.strip().lower()

    def must_not_be_base_branch(**deps):
        candidate = next(iter(deps.values()), None)
        if candidate is None:
            raise ValueError("must_not_be_base_branch: no candidate branch in deps")
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError(f"branch_name must be a non-empty string, got: {candidate!r}")
        norm = candidate.strip().lower()
        if norm == base_norm:
            raise ValueError(
                f"branch_name == base ({base!r}) — refusing. "
                "Branch off the base, don't push directly to it."
            )
        if norm in PROTECTED_BRANCH_NAMES:
            raise ValueError(
                f"branch_name {candidate!r} is a protected name "
                f"({sorted(PROTECTED_BRANCH_NAMES)}) — branch off it instead"
            )
    return must_not_be_base_branch


# ── Public API ─────────────────────────────────────────────────────

def open_pr(
    repo: str,
    branch_name: str,
    title: str,
    body: str,
    files: Iterable[Tuple[str, str]],
    *,
    base: str = "main",
    mergeable_poll_retries: int = 8,
    mergeable_poll_base_ms: int = 2000,
    mergeable_poll_max_ms: int = 8000,
) -> dict:
    """Create a branch, push files, open a PR, poll for mergeable state.

    See SKILL.md for full argument and result shape documentation.
    """
    files_list: List[Tuple[str, str]] = list(files)

    @task(name="determine_branch")
    def determine_branch():
        return branch_name.strip()

    @task(
        name="must_not_be_base_branch_guard",
        depends_on=[determine_branch],
        validate=_must_not_be_base_branch_factory(base),
    )
    def must_not_be_base_branch_guard(determine_branch):
        return determine_branch

    @task(name="get_base_head", depends_on=[must_not_be_base_branch_guard])
    def get_base_head(must_not_be_base_branch_guard):
        sha = _get_branch_head(repo, base)
        return {"base": base, "sha": sha}

    @task(
        name="create_branch",
        depends_on=[must_not_be_base_branch_guard, get_base_head],
    )
    def create_branch(must_not_be_base_branch_guard, get_base_head):
        ref = _create_branch(repo, must_not_be_base_branch_guard, get_base_head["sha"])
        return {
            "branch": must_not_be_base_branch_guard,
            "ref_sha": ref["object"]["sha"],
        }

    @task(name="push_files", depends_on=[create_branch])
    def push_files(create_branch):
        branch = create_branch["branch"]
        pushed = []
        for path, content in files_list:
            resp = _put_file(repo, branch, path, content,
                             message=f"Add {path}")
            commit = resp.get("commit", {}) if isinstance(resp, dict) else {}
            pushed.append({"path": path, "commit_sha": commit.get("sha")})
        return {"branch": branch, "pushed": pushed}

    @task(name="create_pr", depends_on=[push_files])
    def create_pr(push_files):
        pr = _create_pull_request(
            repo, head=push_files["branch"], base=base,
            title=title, body=body,
        )
        return {
            "pr_number": pr["number"],
            "pr_url": pr["html_url"],
            "pr_state": pr.get("state"),
        }

    @task(
        name="wait_mergeable",
        depends_on=[create_pr],
        retry=mergeable_poll_retries,
        retry_backoff_base_ms=mergeable_poll_base_ms,
        retry_max_backoff_ms=mergeable_poll_max_ms,
        retry_until=lambda r: r["mergeable_state"] in SETTLED_MERGEABLE_STATES,
    )
    def wait_mergeable(create_pr):
        pr = _get_pull_request(repo, create_pr["pr_number"])
        return {
            "mergeable_state": pr.get("mergeable_state") or "unknown",
            "mergeable": pr.get("mergeable"),
        }

    @task(name="present_pr", depends_on=[create_pr])
    def present_pr(create_pr):
        print(f"  ✓ PR ready: {create_pr['pr_url']}")
        return create_pr

    flow = Flow(present_pr, wait_mergeable)
    flow.run()

    create_pr_state = flow.results.get(create_pr.name)
    if create_pr_state is None or create_pr_state.state != StepState.SUCCEEDED:
        for r in flow.results.values():
            if r.state == StepState.FAILED and r.error is not None:
                raise RuntimeError(f"open_pr failed at {r.name}: {r.error}") from r.error
        raise RuntimeError("open_pr: PR creation did not succeed")

    def _val(td):
        r = flow.results.get(td.name)
        if r is None or r.state != StepState.SUCCEEDED:
            return None
        return r.value

    pr_payload = create_pr_state.value
    push_payload = _val(push_files) or {}
    base_payload = _val(get_base_head) or {}
    mergeable_state = "unknown"
    mergeable_result = flow.results.get(wait_mergeable.name)
    if mergeable_result is not None and mergeable_result.value is not None:
        mergeable_state = mergeable_result.value.get("mergeable_state", "unknown")

    detached_failures = [(r.name, str(r.error)) for r in flow.detached_failures]

    return {
        "pr_url": pr_payload["pr_url"],
        "pr_number": pr_payload["pr_number"],
        "pr_state": pr_payload.get("pr_state"),
        "branch": branch_name.strip(),
        "base": base,
        "head_sha": base_payload.get("sha"),
        "mergeable_state": mergeable_state,
        "files_pushed": [p["path"] for p in push_payload.get("pushed", [])],
        "detached_failures": detached_failures,
    }
