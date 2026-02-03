# exploring-codebases

A hybrid grep-to-AST retrieval tool.

## Why this architecture wins

*   **Deduplication is Semantic, not Heuristic**:
    *   If grep finds matches on line 10 and line 15, and they are inside the same `def process_data():` function, this tool returns the exact same node object for both hits and collapses them into a single, perfect context block.
*   **Context Boundaries are Absolute**:
    *   The tool returns the entire function body, from `def` to the final `return`, regardless of how many lines it is. No partial thoughts.
*   **Noise Filtering**:
    *   It prioritizes `function_definition` or `class_definition`. If grep hits a comment or a print statement, the AST expansion bubbles up to the parent function.

## Installation

```bash
uv venv /home/claude/.venv
uv pip install tree-sitter-language-pack --python /home/claude/.venv/bin/python
```

## Usage

```bash
/home/claude/.venv/bin/python /mnt/skills/user/exploring-codebases/scripts/search.py "query" /path/to/repo
```

## Supported Languages

- Python
- JavaScript / TypeScript
- Go
- Rust
- Ruby
- Java
- C / C++
- PHP
- C#
