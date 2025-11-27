---
name: mapping-codebases
description: Generate navigable code maps for unfamiliar codebases. Use when exploring a new codebase, needing to understand project structure, or before diving into code modifications. Extracts exports/imports via AST (tree-sitter) to create _MAP.md files per directory. Triggers on "map this codebase", "understand this project structure", "generate code map", or when starting work on an unfamiliar repository.
---

# Mapping Codebases

Generate `_MAP.md` files that provide a hierarchical view of code structure without reading every file.

## Quick Start

```bash
# Install dependencies (once per session)
uv pip install tree-sitter==0.21.3 tree-sitter-languages==1.10.2

# Generate maps for a codebase
python scripts/codemap.py /path/to/repo
```

## What It Produces

Per-directory `_MAP.md` files listing:
- Directory statistics (file count, subdirectory count)
- Subdirectories (with links to their maps)
- Files with exports and imports
- Counts when lists are truncated (e.g., "exports (23)" when showing 8 of 23)

Example output:
```markdown
# auth/
*Files: 3 | Subdirectories: 1*

## Subdirectories
- [middleware/](./middleware/_MAP.md)

## Files
- **jwt.go** — exports: `Claims, ValidateToken` — imports: `context, jwt`
- **handlers.py** — exports (12): `login, logout, refresh_token`... — imports (8): `flask, .models`...
```

## Supported Languages

Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java.

## Commands

```bash
python scripts/codemap.py /path/to/repo                    # Generate maps
python scripts/codemap.py /path/to/repo --skip locale,tests # Skip specific directories
python scripts/codemap.py /path/to/repo --clean             # Remove all _MAP.md
python scripts/codemap.py /path/to/repo -n                  # Dry run (preview)
```

### Skip Patterns

Use `--skip` to exclude directories that add noise without value:

```bash
# Common patterns
--skip locale,migrations,tests              # Django projects
--skip locales,__snapshots__,coverage       # JavaScript projects
--skip target,docs                          # Rust projects
```

Default skip patterns: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `build`, `.next`

## Workflow Integration

1. Run `codemap.py` on the target repo first
2. Read `_MAP.md` at repo root for overview (high-level structure)
3. Navigate to relevant subdirectory maps as needed (drill down)
4. Read actual source files only when necessary

Maps use hierarchical disclosure - you only load what you need. Even massive codebases (1000+ files) stay navigable because each map remains focused on its directory.

## Features

**Directory Statistics**: Each map header shows file and subdirectory counts, helping you quickly assess scope.

**Export/Import Counts**: When truncated, shows total count (e.g., "exports (23)") so you know how much detail exists without cluttering the view.

**Hierarchical Navigation**: Links between maps let you traverse the codebase structure naturally without overwhelming context windows.

**Skip Patterns**: Exclude noise directories (locales with 100+ language subdirs, test snapshots, generated code) to focus maps on actual source code.

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
- Skips: `.git`, `node_modules`, `__pycache__`, `venv`, `dist`, `build` (plus user-specified patterns)
- Private symbols (Python `_prefix`) excluded from exports
