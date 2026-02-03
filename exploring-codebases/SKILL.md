---
name: exploring-codebases
description: Semantic search for codebases. Locates matches with ripgrep and expands them into full AST nodes (functions/classes) using tree-sitter. Returns complete, syntactically valid code blocks rather than fragmented lines. Use when looking for specific implementations, examples, or references where full context is needed.
metadata:
  version: 0.1.0
---

# Exploring Codebases

Hybrid search tool that combines the speed of `ripgrep` with the structural awareness of `tree-sitter`. It finds matches and returns the *entire* function or class containing the match, de-duplicating results semantically.

## Installation

```bash
uv venv /home/claude/.venv
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
```

## Usage

```bash
/home/claude/.venv/bin/python /mnt/skills/user/exploring-codebases/scripts/search.py "query" /path/to/repo
```

## Options

- `--glob pattern`: Filter files (e.g., `*.py`, `*.ts`)
- `--json`: Output JSON for machine processing (default is Markdown)

## Examples

"Find where `User` class is defined"
```bash
/home/claude/.venv/bin/python /mnt/skills/user/exploring-codebases/scripts/search.py "class User" /path/to/repo
```

"Find usage of `process_data` in Python files"
```bash
/home/claude/.venv/bin/python /mnt/skills/user/exploring-codebases/scripts/search.py "process_data" /path/to/repo --glob "*.py"
```
