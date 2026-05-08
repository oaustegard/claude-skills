"""
issue_close.py — Close a GitHub issue with a learning synthesis (flowing graph).

Per github-procedures §7: closing an issue is two artifacts.
  - GitHub Issue = implementation log (scaffolding)
  - Memory       = behavioral learning (building)

The synthesis is what was LEARNED, not what was DONE — the diff already
shows what was done. Synthesis goes both as the closing comment AND as a
`decision`-type memory tagged with `issue-N`, `<repo-short>`.

Usage:

    from muninn_utils.issue_close import issue_close

    result = issue_close(
        number=617,
        synthesis="Refactor pattern X works because of Y. Constraint: Z.",
        repo="oaustegard/claude-skills",
        pending_test=True,
        extra_tags=["flowing", "refactor"],
    )

    # result keys: issue_url, comment_url, memory_id, pending_test_applied,
    #              detached_failures

Internal shape (issue oaustegard/claude-skills#619):

    prepare_synthesis ──▶ close_github_issue           [terminal]
                                  │
                                  └──▶ store_synthesis_memory  [detached]
                                              │
                                              └──▶ verify_pending_test  [detached, when=pending_test]

  - validate=must_have_synthesis_text on prepare_synthesis blocks empty
    or whitespace-only synthesis BEFORE any GitHub API call fires.
  - Caller gets the close ack the moment GitHub returns 2xx; memory write
    happens in the background.
  - pending_test=True is encoded in the initial memory store (cheaper than
    a second write). verify_pending_test is the structural gate that
    surfaces a detached-failure if the tag silently dropped.
  - Memory failure (e.g. proxy 503) doesn't bubble up as an issue-close
    failure — it lands in `result["detached_failures"]`.

Note on graph shape: the originating issue proposed a two-step
"store_synthesis_memory + tag_for_verification" pattern. The remembering
API only exposes `remember(tags=...)` for atomic-write tagging — there is
no public "add tag to existing memory" primitive — so the pending-test
tag is included in the initial store, and `verify_pending_test` is a
read-side assertion that catches silent tag loss (still gated by `when=`).
"""

import json
import os
import urllib.request
from typing import Optional

from flowing import task, Flow, StepState


# ── GitHub helpers ─────────────────────────────────────────────────

def _gh_token():
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _gh_api(method, endpoint, data=None):
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


def _post_close_comment(repo: str, number: int, body: str) -> dict:
    return _gh_api("POST", f"/repos/{repo}/issues/{number}/comments", {"body": body})


def _close_issue(repo: str, number: int, state_reason: str = "completed") -> dict:
    return _gh_api(
        "PATCH", f"/repos/{repo}/issues/{number}",
        {"state": "closed", "state_reason": state_reason},
    )


# ── Memory helpers (lazy import — works whether `scripts` or
# `remembering.scripts` is on sys.path) ────────────────────────────

def _import_remember():
    try:
        from scripts import remember  # type: ignore
        return remember
    except Exception:
        from remembering.scripts import remember  # type: ignore
        return remember


def _import_recall():
    try:
        from scripts import recall  # type: ignore
        return recall
    except Exception:
        from remembering.scripts import recall  # type: ignore
        return recall


# ── Public API ─────────────────────────────────────────────────────

PENDING_TEST_TAG = "pending-test"


def issue_close(
    number: int,
    synthesis: str,
    *,
    repo: str = "oaustegard/claude-skills",
    pending_test: bool = False,
    extra_tags: Optional[list] = None,
    state_reason: str = "completed",
) -> dict:
    """Close a GitHub issue with a synthesis comment, store the synthesis as
    a memory, optionally tag it for later verification.

    Returns dict with:
        issue_url            — https URL of the issue
        comment_url          — html_url of the closing comment, or None
        memory_id            — memory id (str), or None on detached failure
        pending_test_applied — True iff synthesis was tagged for verify
        detached_failures    — list of (task_name, error_str)

    Raises only if the GitHub close itself fails. Memory failures are
    detached and surfaced via `detached_failures`.
    """
    repo_short = repo.rsplit("/", 1)[-1]
    base_tags = [f"issue-{number}", repo_short]
    if extra_tags:
        base_tags.extend(t for t in extra_tags if t and t not in base_tags)

    final_tags = list(base_tags)
    if pending_test and PENDING_TEST_TAG not in final_tags:
        final_tags.append(PENDING_TEST_TAG)

    def must_have_synthesis_text(**deps):
        if not synthesis or not synthesis.strip():
            raise ValueError(
                "synthesis is empty or whitespace — issue_close needs the LEARNING text "
                "(what I learned, not what I did) per github-procedures §7"
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
        name="store_synthesis_memory",
        depends_on=[close_github_issue, prepare_synthesis],
        detached=True,
    )
    def store_synthesis_memory(close_github_issue, prepare_synthesis):
        remember = _import_remember()
        mem_id = remember(
            prepare_synthesis,
            "decision",
            tags=final_tags,
            priority=1,
        )
        return {"memory_id": mem_id, "tags": final_tags}

    @task(
        name="verify_pending_test",
        depends_on=[store_synthesis_memory],
        when=lambda **_: pending_test,
        detached=True,
    )
    def verify_pending_test(store_synthesis_memory):
        mem_id = store_synthesis_memory["memory_id"]
        recall = _import_recall()
        # Try to confirm the memory carries the pending-test tag.
        hits = recall(tags=[PENDING_TEST_TAG], n=20)
        for h in hits:
            if h.get("id") == mem_id:
                return {"verified": True, "memory_id": mem_id}
        raise RuntimeError(
            f"pending-test tag not retrievable on memory {mem_id} — "
            "tag silently dropped or recall index lag"
        )

    flow = Flow(close_github_issue)
    flow.run()

    close_state = flow.results.get(close_github_issue.name)
    if close_state is None or close_state.state != StepState.SUCCEEDED:
        # The main close itself failed — surface it.
        for r in flow.results.values():
            if r.state == StepState.FAILED and r.error is not None:
                raise RuntimeError(
                    f"issue_close: {r.name} failed: {r.error}"
                ) from r.error
        raise RuntimeError("issue_close: close did not succeed and no error was attached")

    def _val(td):
        r = flow.results.get(td.name)
        if r is None or r.state != StepState.SUCCEEDED:
            return None
        return r.value

    closed = close_state.value
    mem_payload = _val(store_synthesis_memory)
    verify_payload = _val(verify_pending_test)
    detached_failures = [(r.name, str(r.error)) for r in flow.detached_failures]

    return {
        "issue_url": closed["issue_url"],
        "comment_url": closed.get("comment_url"),
        "memory_id": mem_payload["memory_id"] if mem_payload else None,
        "pending_test_applied": (verify_payload is not None and verify_payload.get("verified", False)),
        "detached_failures": detached_failures,
    }
