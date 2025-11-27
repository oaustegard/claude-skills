---
name: mapping-codebases
description: Generate navigable code maps for unfamiliar codebases. Use when exploring a new codebase, needing to understand project structure, or before diving into code modifications. Extracts exports/imports via AST (tree-sitter) to create _MAP.md files per directory. Triggers on "map this codebase", "understand this project structure", "generate code map", or when starting work on an unfamiliar repository.
---

# Mapping Codebases

Generate `_MAP.md` files that provide a hierarchical view of code structure without reading every file.

## Quick Start

```bash
# Install dependencies (once per session)
pip install tree-sitter==0.21.3 tree-sitter-languages==1.10.2 --break-system-packages -q

# Generate maps for a codebase
python scripts/codemap.py /path/to/repo
```

## What It Produces

Per-directory `_MAP.md` files listing:
- Subdirectories (with links to their maps)
- Files with exports and imports

Example output:
```markdown
# auth/

## Subdirectories
- [middleware/](./middleware/_MAP.md)

## Files
- **jwt.go** — exports: `Claims, ValidateToken` — imports: `context, jwt`
- **handlers.py** — exports: `login, logout` — imports: `flask, .models`
```

## Supported Languages

Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java.

## Commands

```bash
python scripts/codemap.py /path/to/repo          # Generate maps
python scripts/codemap.py /path/to/repo --clean  # Remove all _MAP.md
python scripts/codemap.py /path/to/repo -n       # Dry run (preview)
```

## Workflow Integration

1. Run `codemap.py` on the target repo first
2. Read `_MAP.md` at repo root for overview
3. Navigate to relevant subdirectory maps as needed
4. Read actual source files only when necessary

## Git Hook (Optional)

For repos where maps should stay fresh:

```bash
# .git/hooks/pre-commit
#!/bin/sh
python /path/to/codemap.py . >/dev/null
git add '*/_MAP.md'
```

## Limitations

- Extracts structural info only (exports/imports), not semantic descriptions
- Skips: `.git`, `node_modules`, `__pycache__`, `venv`, `dist`, `build`
- Private symbols (Python `_prefix`) excluded from exports
