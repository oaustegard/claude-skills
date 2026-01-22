---
name: githubbing
description: GitHub CLI (gh) installation and authenticated operations in Claude.ai containers. Use when user needs to create issues, PRs, view repos, or perform GitHub operations beyond raw API calls.
metadata:
  version: 1.0.0
  requires: configuring
---

# Githubbing

Install and use GitHub CLI (`gh`) for authenticated GitHub operations in Claude.ai container environments.

## When to Use

- Creating/managing issues and PRs
- Repository operations (view, clone via API, releases)
- GitHub Actions workflow management
- Any operation where `gh` CLI is more ergonomic than raw REST API

For simple file fetches from public repos, prefer direct `curl` to raw.githubusercontent.com (no auth needed).

## Setup

### 1. Install gh CLI

```bash
apt-get update -qq && apt-get install -y -qq gh
```

### 2. Configure Authentication

`gh` reads tokens from `GH_TOKEN` or `GITHUB_TOKEN` environment variables.

**Using configuring skill:**
```python
from configuring import get_env
import os

token = get_env("GH_TOKEN") or get_env("GITHUB_TOKEN")
if token:
    os.environ["GH_TOKEN"] = token
```

**Direct sourcing (if token in project files):**
```bash
set -a; . /mnt/project/GitHub.env 2>/dev/null; set +a
```

### 3. Verify

```bash
gh auth status
```

## Token Scopes

| Scope | Enables |
|-------|---------|
| `public_repo` | Public repo operations (issues, PRs, releases) |
| `repo` | Private repo access |
| `read:org` | Organization membership visibility |
| `gist` | Gist operations |

Minimum for most use cases: `public_repo`

## Common Operations

```bash
# View repo info
gh repo view OWNER/REPO --json name,description

# Create issue
gh issue create --repo OWNER/REPO --title "Title" --body "Body"

# List issues
gh issue list --repo OWNER/REPO --state open

# Create PR
gh pr create --repo OWNER/REPO --title "Title" --body "Body" --base main

# View workflow runs
gh run list --repo OWNER/REPO
```

## Relationship to accessing-github-repos

- **accessing-github-repos**: REST API + raw URLs (works without gh CLI)
- **githubbing**: gh CLI wrapper (more ergonomic for complex operations)

Both work through the container's egress proxy. Use whichever fits the task.
