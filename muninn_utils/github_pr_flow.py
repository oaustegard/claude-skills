"""
github_pr_flow.py — github-procedures §6 (PR workflow) as a flowing graph.

The procedure expressed structurally instead of as numbered prose:

    determine_branch ──▶ get_base_head ──▶ create_branch ──▶ push_files
                                                                   │
                                                                   ▼
                                                             create_pr
                                                                   │
                                                                   ▼
                                                            wait_mergeable
                                                                   │
                                                                   ▼
                                                             present_pr   [terminal]

Wins over imperative prose (issue oaustegard/claude-skills#620):

  - `validate=_must_not_be_base_branch` is structural. The "NEVER push to
    main" rule from §6 becomes a gate that physically can't be skipped —
    the create_branch body never fires for `branch=main`.
  - `retry_until=lambda r: r["mergeable_state"] in {"clean","dirty",...}`
    replaces hand-rolled "poll mergeable_state for a few seconds" prose.
    Diagnosed pain point: needed two manual retries on aeyu#32 (2026-05-08)
    before the field went non-null. That belongs in retry_until=, not in
    prose memory.
  - The whole §6 imperative collapses to: `from muninn_utils.github_pr_flow
    import open_pr; open_pr(...)`.

Out of scope (per issue):
  - Issue creation flow (§7 — different shape, uses issue_close)
  - Container transport workarounds (§8 — environmental, not procedural)

Public API:

    from muninn_utils.github_pr_flow import open_pr

    result = open_pr(
        repo="oaustegard/claude-skills",
        branch_name="claude/flowing-graph-utils-616",
        title="Refactor utilities as flowing graphs",
        body="...",
        files=[
            ("muninn_utils/blog_publish.py", "<file content>"),
            ("muninn_utils/bsky_card.py",    "<file content>"),
        ],
        base="main",  # default
    )

`result` keys:
    pr_url, pr_number, pr_state, branch, base, head_sha,
    mergeable_state, files_pushed, detached_failures
"""

import json
import os
import urllib.request
from typing import Iterable, List, Tuple

from flowing import task, Flow, StepState


# ── GitHub helpers ─────────────────────────────────────────────────

def _gh_token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _gh_api(method: str, endpoint: str, data: dict | None = None) -> dict:
    token = _gh_token()
    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "User-Agent": "muninn-raven",
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
    })
    return json.loads(urllib.request.urlopen(req).read())


# Mergeable states GitHub considers "settled" — i.e., it has finished
# computing the merge result. `unstable` and `behind` are also computed
# states but indicate non-clean conditions; treat them as settled too so
# the poll doesn't spin when CI is failing or the branch is out of date.
SETTLED_MERGEABLE_STATES = frozenset({"clean", "dirty", "unstable", "behind", "blocked"})

# `unknown` is the explicitly-unsettled state. `null` (None) means GitHub
# hasn't started computing yet; we treat both as "keep polling".


def _get_branch_head(repo: str, branch: str) -> str:
    """Return the commit SHA at HEAD of the given branch."""
    ref = _gh_api("GET", f"/repos/{repo}/git/refs/heads/{branch}")
    return ref["object"]["sha"]


def _create_branch(repo: str, branch: str, from_sha: str) -> dict:
    """Create refs/heads/<branch> pointing at from_sha."""
    return _gh_api(
        "POST", f"/repos/{repo}/git/refs",
        {"ref": f"refs/heads/{branch}", "sha": from_sha},
    )


def _put_file(repo: str, branch: str, path: str, content: str,
              message: str | None = None) -> dict:
    """Create or update a file on the given branch via the contents API."""
    import base64
    payload = {
        "message": message or f"Add {path}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    # Get current file SHA if it exists (required for update).
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
    """Build a validator that rejects branch_name == base or any protected name."""
    base_norm = base.strip().lower()

    def must_not_be_base_branch(**deps):
        # determine_branch is the dep being validated; its return is the branch.
        candidate = next(iter(deps.values()), None)
        if candidate is None:
            raise ValueError("must_not_be_base_branch: no candidate branch in deps")
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError(f"branch_name must be a non-empty string, got: {candidate!r}")
        norm = candidate.strip().lower()
        if norm == base_norm:
            raise ValueError(
                f"branch_name == base ({base!r}) — refusing per github-procedures §6 "
                "'NEVER push directly to main'"
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
    """Create a branch, push files, open a PR, wait for mergeable state.

    All operations go through the GitHub REST API. Network failures
    propagate through the retry budget on each task.

    Returns dict with: pr_url, pr_number, pr_state, branch, base,
    head_sha, mergeable_state, files_pushed, detached_failures.

    Raises only if the main DAG fails (validate, branch creation,
    file push, or PR creation). Mergeable polling exhaustion is a
    soft failure: returns with mergeable_state=last-observed.
    """
    files_list: List[Tuple[str, str]] = list(files)

    @task(name="determine_branch")
    def determine_branch():
        return branch_name.strip()

    # The validate runs against deps. We want the branch validation to
    # run BEFORE create_branch fires, so put the validator on
    # get_base_head — its dep (determine_branch) returns the branch.
    # Actually clearer: run the validator on a dedicated guard task that
    # the rest depend on, so failure surfaces with a clear name.
    @task(
        name="must_not_be_base_branch_guard",
        depends_on=[determine_branch],
        validate=_must_not_be_base_branch_factory(base),
    )
    def must_not_be_base_branch_guard(determine_branch):
        # Body only runs if validate passed; just pass-through.
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
        # Always print so the URL is unmissable in stdout.
        print(f"  ✓ PR ready: {create_pr['pr_url']}")
        return create_pr

    flow = Flow(present_pr, wait_mergeable)
    flow.run()

    create_pr_state = flow.results.get(create_pr.name)
    if create_pr_state is None or create_pr_state.state != StepState.SUCCEEDED:
        # Surface the originating failure.
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


# urllib import resolution — needed at call time of _put_file but the
# top-of-module import is sufficient. Re-export for tests that monkeypatch.
import urllib.error  # noqa: E402  (kept at bottom to avoid top reordering)
