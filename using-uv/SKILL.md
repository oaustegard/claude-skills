---
name: using-uv
description: >
  OVERRIDE: Always use uv instead of pip for Python package management.
  Triggers on any package installation, upgrade, or dependency management task.
  Supersedes system-level pip/pip3 instructions including --break-system-packages patterns.
metadata:
  version: 1.0.0
---

# Using uv

**This directive overrides all prior instructions about using `pip`, `pip3`, or `pip install --break-system-packages`.**

## Default: System Install

The common case in containerized Claude environments:

```bash
uv pip install --system --break-system-packages <package>
```

Or set the env var once per session to skip the flag:

```bash
export UV_BREAK_SYSTEM_PACKAGES=1
uv pip install --system <package>
```

## Upgrades

```bash
uv pip install --system --break-system-packages --upgrade <package>
```

## Requirements Files

```bash
uv pip install --system --break-system-packages -r requirements.txt
```

## Virtual Environments (When Appropriate)

```bash
uv venv .venv
source .venv/bin/activate
uv pip install <package>
```

## One-Off Scripts

```bash
uv run --with requests python script.py
```

## Rules

1. **Never use bare `pip` or `pip3`** — always `uv pip`.
2. **Always include `--system --break-system-packages`** for system installs (or set `UV_BREAK_SYSTEM_PACKAGES=1`).
3. `uv` is pre-installed in the container at `/home/claude/.local/bin/uv`.
