---
name: tree-sitting
description: Symbol-level navigation of a local checkout using tree-sitter ASTs. Answers where a symbol is defined, what lines it spans, which symbols a file exposes, what a directory holds, and where a name is referenced — every answer carries exact line ranges to feed straight into a scoped read. Use for "where is X defined", "who calls X", "find the function/class named", "what's in this file", "give me the line range for", "show me the source of", "list the symbols in", or before editing a file you have not read. Each invocation auto-scans and is self-contained. Not for first-encounter repo orientation (use exploring-codebases), for what a codebase DOES rather than what it contains (featuring), for binding-resolved Python caller sets (searching-codebases), or for literal text and regex matching (plain ripgrep).
metadata:
  version: 0.10.1
---

# tree-sitting

Tree-sitter symbol index over a local checkout. Every result carries line
ranges, so the next step is a scoped `Read`.

## Setup

Needs Python 3.10+ and `pip install tree-sitter`. On macOS, `/usr/bin/python3`
is 3.9 and will not work; use a Homebrew or uv Python. Grammars are bundled
for Linux x86_64 (`parsers/*.so`) and macOS (`parsers/*.dylib`).

If a file's grammar doesn't load, the file is skipped and stderr prints
`WARNING: no grammar for …` with the fix. Resolve that before trusting an empty
result. On other platforms, run `python3 scripts/build_grammars.py` (needs git
and cc). It writes to `$TREESIT_PARSERS_DIR`, or `~/.cache/tree-sitting/parsers/`
when that is unset, and grammars there take precedence over the bundle.
Installed `tree-sitter-<lang>` wheels are the last fallback.

## Use

`scripts/treesit.py` in this skill's directory scans the repo on every call
(cached on disk; invalidated when files or grammars change), prints a tree
overview, then answers the queries. Batch queries so one scan serves them all.

```bash
python3 scripts/treesit.py REPO                                   # overview, depth 1
python3 scripts/treesit.py REPO --path=src/core --detail=full     # drill in
python3 scripts/treesit.py REPO --no-tree 'find:Parser*' 'source:parse_input' 'refs:ParseState'
```

| Query | Returns |
|---|---|
| `find:PATTERN[:KIND[:LIMIT]]` | symbols by name, substring or glob |
| `symbols:FILE` | every symbol in a file |
| `source:SYMBOL[:FILE]` | the symbol's source |
| `refs:SYMBOL[:LIMIT]` | textual references |
| `imports:FILE` | a file's imports |
| `dir:PATH` | directory overview |

Flags: `--depth N` (-1 = all), `--detail sparse|normal|full`, `--path DIR`,
`--skip DIRS`, `--no-tree`, `--stats`, `--no-cache`, `--rebuild-cache`.
`scripts/engine.py` exposes `CodeCache` for use inside one Python process.

Languages: Python, JavaScript, TypeScript/TSX, Go, Rust, Ruby, Java, C, HTML,
Markdown (heading outline), Mojo. Other languages get generic extraction if
their `tree-sitter-<lang>` wheel is installed.

## Use something else for

- a repo that isn't on disk: `accessing-github-repos`
- what a codebase does: `featuring`
- a first look at an unfamiliar repo: `exploring-codebases`
- binding-resolved Python callers: `searching-codebases --refs`
- literal text or regex: `rg`
