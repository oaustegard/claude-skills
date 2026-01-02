# Comparison: TreeSitter (mapping-codebases) vs. LSP (Serena)

This document compares two approaches to mapping and understanding codebases for coding agents: the **static TreeSitter approach** used in `mapping-codebases` and the **dynamic LSP approach** used in `serena`.

## 1. Architectural Overview

| Feature | TreeSitter Approach (`mapping-codebases`) | LSP Approach (`serena`) |
| :--- | :--- | :--- |
| **Core Technology** | `tree-sitter` (Parsing library) | Language Server Protocol (LSP) |
| **Nature** | **Static Analysis**: Scans files and generates artifacts. | **Dynamic/Interactive**: Client-Server model. |
| **Operation** | "Pre-compute": Generates `_MAP.md` files for the entire codebase upfront. | "On-demand": Agent queries specific files or symbols as needed. |
| **Dependencies** | Minimal (Python + `tree-sitter` bindings). | Heavy (Requires Language Server binaries for each language). |
| **Execution** | Fast, single-pass script. | Slower startup (server init), persistent process. |

## 2. Information Density & Richness

### TreeSitter (`codemap.py`)
*   **Scope:** Focuses on "Exports" and "Imports".
*   **Granularity:** Mostly top-level definitions (Classes, Functions).
*   **Context:**
    *   Extracts names only.
    *   No signatures (params, return types).
    *   No docstrings (usually).
    *   No semantic relationships (doesn't know if `A` inherits from `B`).
*   **Output Format:** Markdown lists (`_MAP.md`). Easy for humans/agents to read sequentially.

### Serena (LSP)
*   **Scope:** Full symbol hierarchy (Project -> File -> Class -> Method -> Variable).
*   **Granularity:** Deep. Includes methods, fields, local variables, interfaces, enums.
*   **Context:**
    *   **Symbol Kinds:** Distinguishes between Class, Interface, Method, Property, etc.
    *   **Signatures:** Often available (depending on LS).
    *   **References:** Can find where a symbol is *used* (Reference counting).
    *   **Diagnostics:** Can report syntax errors or warnings.
*   **Output Format:** Structured JSON objects returned to tool calls (`GetSymbolsOverview`).

## 3. Usefulness for Coding Agents

### TreeSitter Approach
*   **Strengths:**
    *   **Navigation:** Provides a "map" that is always there. The agent can "look around" without calling tools.
    *   **Token Efficiency:** A compact `_MAP.md` is cheaper to read than querying an LS repeatedly for structure.
    *   **Speed:** Instant access. No "waiting for server to initialize".
    *   **Robustness:** Works even if code is broken (syntax errors are tolerated by TreeSitter).
*   **Weaknesses:**
    *   **Shallow:** Agent sees "function `foo` exists" but not what arguments it takes.
    *   **Stale Data:** Maps must be regenerated after changes.

### Serena Approach
*   **Strengths:**
    *   **Precision:** "Go to Definition" and "Find References" are semantically accurate.
    *   **Context:** Agent gets the exact signature and docstring, reducing hallucinations.
    *   **Edit Confidence:** "Rename Symbol" allows safe refactoring across files.
*   **Weaknesses:**
    *   **Discovery Friction:** Agent must *know* to ask. "What files are in this folder?" requires a tool call.
    *   **Complexity:** Setup is harder (installing LSPs).
    *   **Latency:** Tool calls have round-trip time.

## 4. Conclusion & Recommendations

The **TreeSitter approach** is excellent for **high-level navigation and orientation**. It gives the agent a "spatial" sense of the project layout.

The **Serena/LSP approach** is superior for **detailed implementation and refactoring**. It provides the semantic details needed to write correct code.

### Improving `codemap.py`
To bridge the gap, `codemap.py` can be enhanced to borrow some "richness" from the Serena approach without the overhead of LSP:
1.  **Hierarchy:** Extract methods inside classes, not just the class name.
2.  **Symbol Kinds:** Explicitly label symbols (e.g., `(C) MyClass`, `(f) my_method`).
3.  **Signatures:** Extract parameters from the syntax tree to give the agent a hint of usage (e.g., `my_method(a, b)` instead of `my_method`).

This hybrid approach would make the static maps significantly more powerful for "planning" before the agent dives into "editing".
