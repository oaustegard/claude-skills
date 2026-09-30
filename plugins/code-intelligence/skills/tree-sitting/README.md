# tree-sitting

AST-powered code navigation using tree-sitter. Parses all source files in a codebase into in-memory syntax trees, then provides fast query tools for symbol search, file/directory overview, source retrieval, and reference finding.

## Features

- **Fast scanning** — parses ~250 files in ~700ms, then all queries are sub-millisecond from cache
- **Symbol search** — find by exact name, substring, or glob pattern across the entire codebase
- **Directory and file overview** — structural summaries with symbol counts, signatures, and doc comments
- **Source retrieval** — fetch implementation of any symbol, preferring definitions over declarations
- **Reference finding** — locate all textual references to a symbol via fast grep against cached source
- **12 grammars** — Python, JavaScript, TypeScript, TSX, Go, Rust, Ruby, Java, C, HTML, Markdown, Mojo. Bundled for Linux x86_64 (`.so`) and macOS (`.dylib`); `scripts/build_grammars.py` compiles them anywhere else.
- **Three-tier extraction** — custom extractors (richest), community tags.scm queries, and generic heuristic fallback
- **Dual deployment** — direct Python calls in Claude.ai, or long-lived MCP server in Claude Code

## Dependencies

- **tree-sitter** — bare parser runtime
- **Python 3.10+** — the grammars are ABI 15, which needs the tree-sitter >= 0.25 binding
- **fastmcp** — required only for MCP server mode (Claude Code)
