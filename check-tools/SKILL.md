---
name: check-tools
description: Validates development tool installations across Python, Node.js, Java, Go, Rust, C/C++, Git, and system utilities. Use when verifying environments or troubleshooting dependencies.
metadata:
  version: 1.2.0
---

# Check Tools - Development Environment Validator

Reports which development tools are installed and at what version, grouped by
ecosystem. Default behavior reports every tool without failing validation —
suited to diverse PaaS/container environments where only a subset of
ecosystems is expected to be present.

## When to use

- Verifying a container or environment has the tools a task needs
- Troubleshooting a build failure that might be a missing dependency
- Documenting system requirements
- Onboarding: confirming a dev environment is ready

## Running it

```bash
# Fast check with exit code (0 = all required core tools present)
bash assets/check-tools.sh

# Development tools only
bash assets/environment-diagnostic.sh tools

# System info: hardware, mounts, processes
bash assets/environment-diagnostic.sh system

# Complete diagnostic (tools + system + package inventories), written to a file
bash assets/environment-diagnostic.sh full /path/to/report.txt
```

`check-tools.sh` exits non-zero only when a **required** core tool (python3,
pip, node, npm, java, gcc, git, curl, awk, grep, gzip, tar, make, sed) is
missing. Every other tool is reported (✅ found / ⚠️ optional and missing) but
does not fail the run.

## Required vs. optional, by ecosystem

| Ecosystem | Required | Optional |
|-----------|----------|----------|
| Python    | python3, pip | python, uv, poetry, black, mypy, pytest, ruff |
| Node.js   | node, npm | nvm, yarn, pnpm, eslint, prettier, chromedriver |
| Java      | java | mvn, gradle |
| Go        | — | go |
| Rust      | — | rustc, cargo |
| C/C++     | gcc | clang, cmake, ninja, conan |
| Utilities | git, curl, awk, sed, grep, gzip, tar, make | jq, rg, tmux, yq, vim, nano |

Full per-tool version-check commands and installation notes live in
`references/tool-categories.md`.

## Files

- `assets/check-tools.sh` — fast validation script (exit codes, quick checks)
- `assets/environment-diagnostic.sh` — comprehensive diagnostic with
  `tools` / `system` / `full` modes
- `references/tool-categories.md` — detailed per-tool breakdown and
  installation instructions

## Extending

The required/optional split lives in `assets/check-tools.sh`
(`check_required_tool` / `check_optional_tool` calls), not in this file — to
change which tools are required, edit the script.
