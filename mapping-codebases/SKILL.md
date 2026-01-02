---
name: mapping-codebases
description: Generate navigable code maps for unfamiliar codebases. Use when exploring a new codebase, needing to understand project structure, or before diving into code modifications. Extracts exports/imports via AST (tree-sitter) to create _MAP.md files per directory. Triggers on "map this codebase", "understand this project structure", "generate code map", or when starting work on an unfamiliar repository.
metadata:
  version: 0.3.0
---

# Mapping Codebases

Generate `_MAP.md` files that provide a hierarchical view of code structure without reading every file.

## Quick Start

```bash
# Install dependencies (once per session)
uv pip install tree-sitter-language-pack

# Generate maps for a codebase
python scripts/codemap.py /path/to/repo
```

## What It Produces

Per-directory `_MAP.md` files listing:
- Directory statistics (file count, subdirectory count)
- Subdirectories (with links to their maps)
- **Symbol hierarchy** with kind markers: (C) class, (m) method, (f) function
- **Function signatures** extracted from AST (Python, partial TypeScript)
- Import previews

Example output:
```markdown
# auth/
*Files: 3 | Subdirectories: 1*

## Subdirectories
- [middleware/](./middleware/_MAP.md)

## Files

### handlers.py
> Imports: `flask, functools, jwt, .models`...
- **login** (f) `(username: str, password: str)`
- **logout** (f) `()`
- **AuthHandler** (C)
  - **__init__** (m) `(self, config: dict)`
  - **validate_token** (m) `(self, token: str)`
  - **refresh_session** (m) `(self, user_id: int)`
```

## Supported Languages

Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java, HTML.

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

**Symbol Hierarchy**: Shows classes with nested methods, not just flat lists. See the structure at a glance with kind markers (C/m/f).

**Function Signatures**: Extracts parameter lists from Python and partial TypeScript, showing what functions expect without reading the source.

**Directory Statistics**: Each map header shows file and subdirectory counts, helping you quickly assess scope.

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

- Extracts structural info only (symbols/imports), not semantic descriptions
- Method extraction: Full support for Python/TypeScript, partial for other languages
- Signatures: Python (full), TypeScript (partial), others (not extracted)
- Skips: `.git`, `node_modules`, `__pycache__`, `venv`, `dist`, `build` (plus user-specified patterns)
- Private symbols (Python `_prefix`) excluded from top-level exports (methods not filtered yet)
