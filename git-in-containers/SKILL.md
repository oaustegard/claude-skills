---
name: git-in-containers
description: Git repository access in containerized AI chat environments. Use when user requests git clone, repo fetching, or GitHub operations in web/mobile AI chat sessions.
metadata:
  version: 1.0.0
---

# Git in Container Environments

**IMPORTANT**: This skill is for containerized AI chat environments (web, iOS, Android) only. Native development environments have direct git access and do not need these workarounds.

## The Problem

**git clone does not work** in containerized AI environments. The egress proxy blocks git protocol even for whitelisted domains (401 on CONNECT tunnel).

## Workaround: raw.githubusercontent.com

Fetch individual files via curl:

```bash
curl -sL https://raw.githubusercontent.com/OWNER/REPO/BRANCH/path/to/file.py
```

### Example: Fetch a Python script

```bash
curl -sL https://raw.githubusercontent.com/anthropics/anthropic-sdk-python/main/src/anthropic/__init__.py
```

## Fetching Directory Structure

Use GitHub Tree API to get directory listings:

```bash
curl -sL https://api.github.com/repos/OWNER/REPO/git/trees/BRANCH?recursive=1
```

This returns JSON with all files and their paths. You can then fetch files individually.

### Example: Browse a repository

```bash
# Get the tree
curl -sL https://api.github.com/repos/oaustegard/claude-skills/git/trees/main?recursive=1 | \
  python3 -c "import json, sys; [print(f['path']) for f in json.load(sys.stdin)['tree']]"

# Fetch specific files
curl -sL https://raw.githubusercontent.com/oaustegard/claude-skills/main/README.md
```

## Network Requirements

Domain `raw.githubusercontent.com` must be in project network allowlist.

If curl fails with `host_not_allowed`:
1. Inform user: `raw.githubusercontent.com` needs to be added to project network settings
2. Settings change requires new conversation to take effect

## Do Not

- **Never** attempt `git clone` (wastes time, always fails)
- **Never** suggest workarounds requiring git protocol
- **Never** retry with different git flags or SSH URLs
- **Never** recommend git submodules, git archive, or other git-protocol operations

## Alternative: Use MCP GitHub Integration

If available, the MCP GitHub server provides programmatic access to repositories without network restrictions.

## When This Skill Does Not Apply

- **Native development environments**: Have direct git access via proxy, use standard git commands
- **Local environments**: git clone works normally
- **Environments with git protocol access**: Use native git tools
