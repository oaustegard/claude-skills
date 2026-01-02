# mapping-codebases

Generate navigable code maps for unfamiliar codebases. Use when exploring a new codebase, needing to understand project structure, or before diving into code modifications. Extracts exports/imports via AST (tree-sitter) to create `_MAP.md` files per directory.

## Features

*   **Fast & Deterministic:** Uses `tree-sitter` for static analysis. No LLM calls.
*   **Rich Maps:** Extracts top-level definitions (Functions, Classes) and nested members (Methods).
*   **Context:** Captures symbol kinds (Class, Method, Function) and signatures (where possible) to aid agent understanding.
*   **Navigation:** Generates linked `_MAP.md` files in each directory.

## Requirements

*   **Python 3.10+**
*   **tree-sitter-language-pack** - Maintained fork with 165+ language grammars

## Installation

**In Claude Code environments (preferred):**

```bash
uv pip install --system tree-sitter-language-pack
```

**In other environments:**

```bash
# With uv
uv pip install tree-sitter-language-pack

# Or with pip
pip install tree-sitter-language-pack
```

**Why uv?** Claude Code environments have uv pre-installed for efficient package management. Using uv with `--system` flag is faster and preferred.

## Usage

```bash
python3 scripts/codemap.py [path/to/codebase]
```

To clean up all `_MAP.md` files:

```bash
python3 scripts/codemap.py --clean
```
