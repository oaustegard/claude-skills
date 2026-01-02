# mapping-codebases

Generate navigable code maps for unfamiliar codebases. Use when exploring a new codebase, needing to understand project structure, or before diving into code modifications. Extracts exports/imports via AST (tree-sitter) to create `_MAP.md` files per directory.

## Features

*   **Fast & Deterministic:** Uses `tree-sitter` for static analysis. No LLM calls.
*   **Rich Maps:** Extracts top-level definitions (Functions, Classes) and nested members (Methods).
*   **Context:** Captures symbol kinds (Class, Method, Function) and signatures (where possible) to aid agent understanding.
*   **Navigation:** Generates linked `_MAP.md` files in each directory.

## Installation

This tool requires `tree-sitter` and `tree-sitter-languages`. Note that `tree-sitter-languages` may require specific versions of `tree-sitter`.

```bash
pip install "tree-sitter==0.21.3" tree-sitter-languages
```

## Usage

```bash
python3 scripts/codemap.py [path/to/codebase]
```

To clean up all `_MAP.md` files:

```bash
python3 scripts/codemap.py --clean
```
