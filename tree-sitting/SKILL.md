---
name: tree-sitting
description: AST-powered code navigation via tree-sitter. Parses codebases into in-memory ASTs and exposes query tools for symbol search, file/directory overview, source retrieval, and references. Use when exploring unfamiliar repos, navigating code, or needing fast symbol lookup. Replaces serial file reads with sub-millisecond cached queries. Triggers on "map this codebase", "explore repo", "find symbol", "navigate code", "tree-sitter", or when starting work on an unfamiliar repository.
metadata:
  version: 0.2.0
---

# tree-sitting

AST-powered code navigation using tree-sitter. Parses all source files into in-memory syntax trees, then provides fast query tools. One scan (~700ms for a 250-file repo), then all queries are sub-millisecond.

## Setup

```bash
uv venv /home/claude/.venv 2>/dev/null
uv pip install tree-sitter-language-pack fastmcp --python /home/claude/.venv/bin/python
```

Total install: <2s cold cache, <400ms warm.

## Usage: Claude.ai (direct calls)

```bash
cd /mnt/skills/user/tree-sitting/scripts
/home/claude/.venv/bin/python -c "
import sys; sys.path.insert(0, '.')
from engine import cache

stats = cache.scan('/path/to/repo')
print(cache.tree_overview())
print(cache.find_symbol('ClassName'))
print(cache.dir_overview('src/core'))
print(cache.file_symbols('src/core/parser.c'))
print(cache.get_source_range('src/core/parser.c', 100, 150))
"
```

Multiple queries in one bash call = one parse cost + N × <1ms queries.

## Usage: Claude Code (MCP server)

Add to Claude Code MCP config:

```json
{
  "mcpServers": {
    "tree-sitting": {
      "command": "/path/to/.venv/bin/python",
      "args": ["/path/to/tree-sitting/scripts/server.py"],
      "cwd": "/path/to/tree-sitting/scripts"
    }
  }
}
```

The server persists between tool calls — scan once, query many times.

### MCP Tools

| Tool | Purpose |
|------|---------|
| `scan` | Parse codebase into ASTs. Call first. ~700ms for 250 files. |
| `tree_overview` | Directory tree with file/symbol counts. First orientation. |
| `dir_overview` | Files + top symbols for one directory. Dynamic _MAP.md. |
| `find_symbol` | Search by name/substring/glob across codebase. |
| `file_symbols` | All symbols in a file with signatures and docs. |
| `get_source` | Source code of a specific symbol. Prefers implementation over declaration. |
| `references` | Find all textual references to a symbol. Fast grep against cached source. |

### Workflow

```
1. scan("/path/to/repo")           → parse everything, build index
2. tree_overview()                  → orient: what dirs, how big, what languages
3. dir_overview("src/core")         → drill into interesting directory
4. find_symbol("Parser*")           → find specific symbols
5. file_symbols("src/core/parser.c") → see full API of a file
6. get_source("parse_input")        → read the implementation
7. references("ParseState")         → find usage across codebase
```

## Supported Languages

Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java, C, C++, C#, Swift, Kotlin, Scala, HTML, CSS, Markdown, JSON, YAML, TOML, Lua, Bash, Elisp, Zig, Elixir.

Three-tier extraction:

1. **Custom extractors** (richest — signatures, hierarchy, docstrings): Python, C
2. **tags.scm queries** (community-maintained — kinds, docs where grammars support it): Rust, Go, JavaScript, TypeScript, TSX, Ruby, Java, C++, C#
3. **Generic heuristic** (names + kinds + locations): all others

tags.scm queries use the same patterns maintained by tree-sitter grammar repos, giving correct symbol classification (e.g. Rust `impl` methods vs free functions, Go interfaces vs structs) without hand-written extractors.

## What It Extracts

- **Symbols**: functions, classes, structs, enums, methods, constants, defines, types
- **Signatures**: parameter lists and return types (Python, C; partial for others)
- **Doc comments**: first-line summaries from docstrings, JSDoc, Doxygen, `///`, `#` 
- **Line ranges**: start and end line for every symbol
- **Imports**: per-file dependency tracking
- **Hierarchy**: class→methods, struct→fields (Python, C)

## Architecture

```
CodeCache (in-memory singleton)
  ├── files: {relpath → FileEntry(source, tree, symbols, imports)}
  ├── _symbol_index: {name → [Symbol, ...]}  ← fast lookup
  └── methods: scan(), find_symbol(), file_symbols(), dir_overview(), ...
       │
       ├── FastMCP server (Claude Code) — long-lived process, stdio transport
       └── Direct Python calls (Claude.ai) — one bash invocation per query batch
```

Parse cost is paid once. The symbol index enables O(1) exact match and O(n) substring/glob search where n is the number of unique symbol names (not files).
