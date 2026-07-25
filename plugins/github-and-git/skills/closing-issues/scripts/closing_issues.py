"""
closing_issues — close a GitHub issue with a synthesis comment as a
flowing graph, with an optional pluggable post-close callback.

The synthesis text is `validate=`d upfront; the close happens against
the GitHub API; an optional callback runs `detached=True` so its
failure doesn't bubble up as a close failure.

See SKILL.md for the full picture.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable, Optional

# The flowing skill is canonical. Try the package layout first; fall
# back to importing it from the canonical install path.
try:
    from flowing import task, Flow, StepState  # type: ignore
except ImportError:  # pragma: no cover — defensive only
    import importlib.util as _ilu
    import sys as _sys
    _SKILL = "/mnt/skills/user/flowing/scripts/flowing.py"
    if not os.path.exists(_SKILL):
        raise ImportError(
            "closing_issues requires the flowing skill at "
            f"{_SKILL} or `from flowing import ...` on the python path"
        )
    _spec = _ilu.spec_from_file_location("flowing", _SKILL)
    _flow = _ilu.module_from_spec(_spec)
    _sys.modules["flowing"] = _flow
    _spec.loader.exec_module(_flow)
    task, Flow, StepState = _flow.task, _flow.Flow, _flow.StepState


# ── GitHub helpers ─────────────────────────────────────────────────

GITHUB_USER_AGENT = "closing-issues"


def _gh_token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _gh_api(method: str, endpoint: str, data: dict | None = None) -> dict:
    token = _gh_token()
    if not token:
        raise RuntimeError(
            "GH_TOKEN (or GITHUB_TOKEN) not set — closing-issues needs an "
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


def _post_close_comment(repo: str, number: int, body: str) -> dict:
    return _gh_api("POST", f"/repos/{repo}/issues/{number}/comments", {"body": body})


def _close_issue(repo: str, number: int, state_reason: str = "completed") -> dict:
    return _gh_api(
        "PATCH", f"/repos/{repo}/issues/{number}",
        {"state": "closed", "state_reason": state_reason},
    )


# ── Public API ─────────────────────────────────────────────────────

def close_issue(
    repo: str,
    number: int,
    synthesis: str,
    *,
    post_close_callback: Optional[Callable] = None,
    state_reason: str = "completed",
) -> dict:
    """Close a GitHub issue with a synthesis comment.

    See SKILL.md for full argument and result shape documentation.
    """
    def must_have_synthesis_text(**deps):
        if not synthesis or not synthesis.strip():
            raise ValueError(
                "synthesis is empty or whitespace — close_issue needs the "
                "LEARNING text. The diff already shows what was done."
            )

    @task(name="prepare_synthesis", validate=must_have_synthesis_text)
    def prepare_synthesis():
        return synthesis.strip()

    @task(name="close_github_issue", depends_on=[prepare_synthesis])
    def close_github_issue(prepare_synthesis):
        comment = _post_close_comment(repo, number, prepare_synthesis)
        _close_issue(repo, number, state_reason=state_reason)
        return {
            "issue_url": f"https://github.com/{repo}/issues/{number}",
            "comment_url": comment.get("html_url"),
            "comment_id": comment.get("id"),
        }

    @task(
        name="post_close_callback",
        depends_on=[close_github_issue, prepare_synthesis],
        when=lambda **_: post_close_callback is not None,
        detached=True,
    )
    def post_close_callback_node(close_github_issue, prepare_synthesis):
        # mypy-style guard: when= would have skipped if None.
        cb = post_close_callback
        return cb(
            synthesis=prepare_synthesis,
            issue_url=close_github_issue["issue_url"],
            repo=repo,
            number=number,
        )

    flow = Flow(close_github_issue)
    flow.run()

    close_state = flow.results.get(close_github_issue.name)
    if close_state is None or close_state.state != StepState.SUCCEEDED:
        for r in flow.results.values():
            if r.state == StepState.FAILED and r.error is not None:
                raise RuntimeError(
                    f"close_issue: {r.name} failed: {r.error}"
                ) from r.error
        raise RuntimeError("close_issue: close did not succeed")

    closed = close_state.value
    cb_state = flow.results.get(post_close_callback_node.name)
    callback_result = (
        cb_state.value
        if cb_state is not None and cb_state.state == StepState.SUCCEEDED
        else None
    )
    detached_failures = [(r.name, str(r.error)) for r in flow.detached_failures]

    return {
        "issue_url": closed["issue_url"],
        "comment_url": closed.get("comment_url"),
        "comment_id": closed.get("comment_id"),
        "callback_result": callback_result,
        "detached_failures": detached_failures,
    }
