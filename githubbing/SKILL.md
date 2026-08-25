---
name: githubbing
description: >-
  Installs and authenticates the GitHub CLI (gh) in a Claude.ai container,
  then runs gh commands against it. Use for "install gh", "gh auth", "create
  an issue or PR from the CLI", "gh is not authenticated", or any GitHub
  operation you want to issue as a gh command rather than a raw API call.
  This skill is the transport rather than the analysis. To understand what a
  repository does or contains, use exploring-codebases; to add a repo to the
  session, accessing-github-repos.
metadata:
  version: 1.2.0
  requires: configuring
---

# Githubbing

Install and use GitHub CLI (`gh`) for authenticated GitHub operations.

## 1. Install

```bash
bash /path/to/githubbing/scripts/install-gh.sh
```

## 2. Configure Authentication

`gh` reads tokens from `GH_TOKEN` or `GITHUB_TOKEN` environment variables.

```python
from configuring import get_env
import os

token = get_env("GH_TOKEN") or get_env("GITHUB_TOKEN")
if token:
    os.environ["GH_TOKEN"] = token
```

## 3. Verify

```bash
gh auth status
```
