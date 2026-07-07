---
name: mapping-codebases
description: Generate navigable code maps for unfamiliar codebases. Extracts exports/imports via AST (tree-sitter) to create _MAP.md files per directory showing classes, functions, methods with signatures and line numbers. Use when exploring repositories, understanding project structure, analyzing unfamiliar code, or before modifications. Triggers on "map this codebase", "explore repo", "understand structure", "what does this project contain", or when starting work on an unfamiliar repository.
metadata:
  version: 0.8.0
---

# Mapping Codebases

Generate `_MAP.md` files providing hierarchical code structure views. Maps show function signatures, class methods, imports, and line numbers—enabling API understanding without reading full source files.

## Installation

```bash
uv venv /home/claude/.venv
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
```

**Bundled parsers**: The skill includes pre-built parsers for all 11 supported languages (Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java, C, HTML, Markdown) in `parsers/`. These are used automatically when the tree-sitter-language-pack runtime download fails (e.g., in proxied environments). No network access needed for supported languages.

## Generate Maps

```bash
/home/claude/.venv/bin/python /mnt/skills/user/mapping-codebases/scripts/codemap.py /path/to/repo --skip tests,.github,locale
```

Common skip patterns: `tests,.github,.husky,locale,migrations,__snapshots__,coverage,target,docs`

## Navigate Via Maps

After generating maps, use them for navigation—read `_MAP.md` files, not source files directly.

**Workflow:**
1. Read root `_MAP.md` for high-level structure
2. Follow subdirectory links to drill into relevant areas
3. Use function signatures and class methods to understand APIs
4. Read full source only when implementation details are needed

**Maps reveal without reading source:**
- All public functions with signatures: `def record_attempt(subtask_id, session, success, approach, error=None)` :200
- Class structure with methods: `RecoveryManager` → `classify_failure()`, `is_circular_fix()`, `rollback_to_commit()`
- Import relationships showing module dependencies
- Line numbers for direct navigation

**Anti-pattern:** Reading files directory-by-directory. Use maps to find what you need, then read only the specific file/lines required.

## Map Contents

Each `_MAP.md` includes:
- Directory statistics (file/subdirectory counts)
- Subdirectory links for hierarchical navigation
- Per-file: imports preview, symbol hierarchy with (C)lass/(m)ethod/(f)unction markers
- Function signatures (Python, TypeScript, Go, Rust, Ruby, C)
- Line ranges (`:42-85` format) showing symbol start and end lines
- Doc comments — first-line summaries from docstrings, JSDoc, Doxygen, `///`, `#` comments
- Constants and defines (`pub const`, `#define`, `export const`, Go `const`)
- Enum variants as children of enum symbols (C)
- Markdown files: h1/h2 heading ToC
- Other files section (JSON, YAML, configs)

Example:
```markdown
# services/
*Files: 4 | Subdirectories: 0*

## Files

### recovery.py
> Imports: `json, subprocess, dataclasses, datetime, enum`...
- **FailureType** (C) :24-38
- **RecoveryManager** (C) :43-510 — Manages error recovery strategies.
  - **__init__** (m) `(self, spec_dir: Path, project_dir: Path)` :55-72
  - **classify_failure** (m) `(self, error: str, subtask_id: str)` :137-198 — Classify an error into a FailureType.
  - **record_attempt** (m) `(subtask_id, session, success, approach, error=None)` :200-240
  - **is_circular_fix** (m) `(self, subtask_id: str, current_approach: str)` :242-280
  - **get_recovery_hints** (m) `(self, subtask_id: str)` :495-510
```

## Commands

```bash
# Generate maps
/home/claude/.venv/bin/python /mnt/skills/user/mapping-codebases/scripts/codemap.py /path/to/repo

# Skip directories
/home/claude/.venv/bin/python /mnt/skills/user/mapping-codebases/scripts/codemap.py /path/to/repo --skip tests,.github

# Clean maps
/home/claude/.venv/bin/python /mnt/skills/user/mapping-codebases/scripts/codemap.py /path/to/repo --clean

# Dry run
/home/claude/.venv/bin/python /mnt/skills/user/mapping-codebases/scripts/codemap.py /path/to/repo -n

# Verbose (debug output)
/home/claude/.venv/bin/python /mnt/skills/user/mapping-codebases/scripts/codemap.py /path/to/repo -v
```

Default skips: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `build`, `.next`

## Supported Languages

Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java, C, HTML, Markdown.

## Limitations

- Doc comments extracted as first-line summaries (not full descriptions)
- Signatures: Python (full), TypeScript/Go/Rust/Ruby/C (params + return types), Java (not extracted)
- Markdown: h1/h2 headings only
- Private symbols (`_prefix`) excluded from top-level exports
