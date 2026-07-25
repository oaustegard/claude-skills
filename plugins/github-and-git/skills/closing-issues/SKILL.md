---
name: closing-issues
description: Close a GitHub issue with a synthesis comment as a flowing graph — validate the synthesis, post the closing comment, close, then run a pluggable callback (e.g. memory store) detached. Use when closing an issue should also capture the LEARNING (not just the diff log) and when the post-close work shouldn't block the close ack.
metadata:
  version: 0.1.0
  requires: flowing
---

# Closing Issues

A `flowing` graph that turns "close GitHub issue + capture what I learned"
into a structural DAG. The synthesis text is validated upfront, the close
happens against the GitHub API, and an optional post-close callback runs
detached so the close ack is unblocked.

```python
from closing_issues import close_issue

result = close_issue(
    repo="owner/repo",
    number=42,
    synthesis=(
        "Pattern X works because of Y. Constraint: don't apply to Z. "
        "Future note: revisit when feature Q lands."
    ),
)

print(result["issue_url"])    # https://github.com/.../issues/42
print(result["comment_url"])  # ...#issuecomment-...
```

## Why a synthesis, not a "done" comment

Closing an issue produces two artifacts:

- **The Issue itself** — implementation log. The diff and commit history
  already show *what* was done.
- **The closing comment / synthesis** — what was *learned*. Lasts longer
  than the diff in mental cache.

Good closing comments lead with *why*, not *what*. Failure modes,
constraints discovered, alternatives rejected. The synthesis is the
seed of an institutional memory.

## Internal shape

```
prepare_synthesis ──▶ close_github_issue           [terminal]
                              │
                              └──▶ post_close_callback  [detached, when=callback]
```

- **`validate=must_have_synthesis_text`** runs against the raw input
  string. Empty or whitespace-only → FAILED with no GitHub API call.
  This is structural: callers can't accidentally close-with-no-text.

- **`close_github_issue`** posts the synthesis as a comment, then
  PATCHes the issue to `state=closed, state_reason=completed`. Returns
  the issue URL and comment URL.

- **`post_close_callback`** (optional) runs detached. Caller plugs in
  any extra work — store synthesis in a memory system, ping a tracker,
  emit a webhook. Failure here lands in `result["detached_failures"]`
  and does NOT bubble up as a close failure. Skipped via `when=` if
  the callback isn't provided.

## Pluggable post-close callback

```python
def store_in_my_memory(synthesis: str, issue_url: str, repo: str, number: int):
    # Whatever your memory layer is — Turso, sqlite, a JSON file, etc.
    db.execute("INSERT INTO learnings (issue, synthesis) VALUES (?, ?)",
               (issue_url, synthesis))
    return {"stored": True}

result = close_issue(
    repo="owner/repo",
    number=42,
    synthesis="...",
    post_close_callback=store_in_my_memory,
)

if result["callback_result"] is None and result["detached_failures"]:
    # The callback failed but the issue is still closed.
    print("Memory store failed:", result["detached_failures"])
```

The callback receives keyword arguments: `synthesis`, `issue_url`,
`repo`, `number`. Anything it returns goes into
`result["callback_result"]`.

## Result shape

```python
{
    "issue_url":        "https://github.com/owner/repo/issues/N",
    "comment_url":      "https://github.com/.../issues/N#issuecomment-...",
    "comment_id":       12345,
    "callback_result":  <whatever the callback returned, or None>,
    "detached_failures": [],   # populated if callback raised
}
```

Raises `RuntimeError` only if the GitHub close itself fails. Callback
failures are detached.

## Auth

Requires `GH_TOKEN` (or `GITHUB_TOKEN`) in the environment. Classic PAT
or fine-grained PAT with `repo` scope (specifically `issues:write`).

## When NOT to use

- Closing an issue without a synthesis. If you genuinely have nothing
  to say beyond "done," just `gh issue close N` directly. This skill
  is for the synthesis use case.
- Closing many issues at once (use a script that calls this in a loop —
  fine, but the flow setup cost per call is small but not zero).

## See also

- `flowing` — the DAG runner this skill is built on
- `opening-prs` — the symmetric "open and merge" flow
