---
name: opening-prs
description: Open a GitHub PR via API as a flowing graph — branch + push + create_pr + mergeable poll, with structural protection against pushing to main/master/etc. Use when a Claude Code or Claude.ai container needs to land changes on GitHub via the API (no git CLI required) and the prose "create branch, push, open PR, wait for mergeable" workflow keeps drifting under context pressure.
metadata:
  version: 0.1.0
  requires: flowing
---

# Opening PRs

A `flowing` graph that turns the imperative "create branch, push files,
open a PR, poll mergeable_state" workflow into a structural DAG. The
"NEVER push directly to main" rule is encoded as a `validate=` gate that
physically can't be skipped.

```python
from opening_prs import open_pr

result = open_pr(
    repo="owner/repo",
    branch_name="feat/cool-thing",
    title="Add cool thing",
    body="## Summary\n\n...",
    files=[
        ("src/cool.py", "<file content>"),
        ("docs/cool.md", "<file content>"),
    ],
    base="main",  # default; protected names are also rejected
)

print(result["pr_url"])             # https://github.com/.../pull/N
print(result["mergeable_state"])    # clean | dirty | unstable | behind | blocked
```

## What this fixes

The `gh pr create` workflow (or hand-rolled API calls) has five steps in
prose form:

1. Determine the branch name
2. Get the base branch's HEAD SHA
3. Create the branch
4. Push files to the branch
5. Create the PR
6. Poll `mergeable_state` until GitHub finishes computing it

Each step has known failure modes:

- **Step 1**: Accidentally pushing to `main` — the diagnosed pattern that
  motivated github-procedures §6 in the first place.
- **Step 6**: GitHub returns `mergeable_state: null` immediately after
  creation. Need to poll. "Wait a few seconds and check" is prose, not a
  procedure — so it gets skipped under context pressure.

This skill encodes both as flowing primitives:

```
determine_branch ──▶ guard ──▶ get_base_head ──▶ create_branch
                      │                              │
                      │                              ▼
                      │                        push_files
                      │                              │
                      │                              ▼
                      │                         create_pr
                      │                          /        \
                      │                         ▼          ▼
                      │                  wait_mergeable  present_pr [terminal]
                      │
                      └─ validate=must_not_be_base_branch
```

- **`validate=must_not_be_base_branch`** rejects `branch_name in
  {"main", "master", "trunk", "production", "prod"}` — case-insensitive
  — and the configured `base` itself. The body of `create_branch` never
  fires for a protected name. No GitHub API call happens for an
  invalid branch name.

- **`retry_until=lambda r: r["mergeable_state"] in SETTLED_STATES`**
  consumes the retry budget while GitHub computes the merge result.
  `unknown` and `null` keep polling; settled states (`clean`, `dirty`,
  `unstable`, `behind`, `blocked`) stop. Exhaustion is soft: the PR is
  still presented with the last observed state.

## Auth

Requires `GH_TOKEN` (or `GITHUB_TOKEN`) in the environment. Classic PAT
or fine-grained PAT with `repo` scope.

```python
import os
os.environ["GH_TOKEN"] = "ghp_..."   # or load from a .env file
```

The skill sends `User-Agent: opening-prs` on every API call. (GitHub
returns 401 "Bad credentials" without a UA, regardless of token
validity. Common trap.)

## Result shape

```python
{
    "pr_url": "https://github.com/owner/repo/pull/N",
    "pr_number": 42,
    "pr_state": "open",
    "branch": "feat/cool-thing",
    "base": "main",
    "head_sha": "abc123...",
    "mergeable_state": "clean",
    "files_pushed": ["src/cool.py", "docs/cool.md"],
    "detached_failures": [],
}
```

Raises `RuntimeError` only if the main DAG fails (validate, branch
creation, file push, or PR creation). Mergeable polling exhaustion is a
soft failure — the PR exists, the field just isn't computed yet.

## Tuning the mergeable poll

```python
open_pr(
    ...,
    mergeable_poll_retries=8,         # default 8
    mergeable_poll_base_ms=2000,      # default 2s
    mergeable_poll_max_ms=8000,       # default 8s (cap on exponential backoff)
)
```

## When NOT to use

- Pushing many large files (the GitHub Contents API is one-file-per-PUT
  with base64 encoding — slow above ~10 files). Use `git push` if you
  have the CLI.
- Needing to amend commits or rewrite history. This skill creates one
  commit per file via the contents API.
- Anything involving force-push, branch deletion, or PR review-state
  manipulation. Out of scope; use a different tool.

## See also

- `flowing` — the DAG runner this skill is built on
- `closing-issues` — the symmetric "close + synthesize" flow
- The `accessing-github-repos` skill for byte-layer GitHub access patterns
