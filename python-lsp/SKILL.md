---
name: python-lsp
description: Semantic Python code queries via a stdio LSP client driving pyright-langserver. Provides binding-resolved go-to-definition, find-references, hover types, type diagnostics, file symbol outlines, and project-wide symbol search — name resolution and type inference that tree-sitter and ripgrep cannot do. Use when you need to follow an import to a definition, find all real uses of a symbol (excluding same-named-but-unrelated ones), get an inferred type, surface type errors, outline a file, or search symbols across a project. Triggers on "go to definition", "find references", "what type is", "resolve this symbol", "symbol outline", "find symbol in project", "pyright", "type-check this file".
metadata:
  version: 0.2.0
---

# python-lsp

A thin, dependency-free Python client that owns the LSP lifecycle against
`pyright-langserver --stdio` and exposes high-value semantic queries.

**Why, over tree-sitter / ripgrep:** tree-sitter gives a CST — structural
queries, call-site enumeration by name. It cannot do name resolution, type
inference, or cross-file binding. ripgrep matches text, so it false-positives
on shadowed / same-named symbols. pyright resolves bindings. This client is
that semantic overlay.

## Setup (self-installing)

The client bootstraps pyright on first use. Run the bootstrap explicitly, or
let `LSPClient` do it via `ensure_pyright()`:

```sh
sh /mnt/skills/user/python-lsp/scripts/bootstrap.sh
# or, equivalently, the one-liner it wraps:
command -v pyright-langserver >/dev/null || uv tool install pyright
```

pyright wheels vendor the langserver JS bundle and run it on **system node** —
no npm install, no separate fetch when node is present. Measured cold (caches
wiped): `uv tool install pyright` ~0.7s, first working server ~1.8s total; warm
sub-second.

**Node prerequisite.** The clean path assumes system `node` (v18+) is present.
With no node, pyright-python falls back to downloading node from nodejs.org,
which may be blocked in locked-down containers. The bootstrap detects node and
**fails loudly** (exit 1, clear message) rather than hanging.

## Usage: CLI

```bash
LSP=/mnt/skills/user/python-lsp/scripts/lsp_client.py

python3 $LSP bootstrap                              # ensure pyright installed
python3 $LSP <root> definition  <file> <line> <col>
python3 $LSP <root> references  <file> <line> <col>
python3 $LSP <root> hover       <file> <line> <col>
python3 $LSP <root> diagnostics <file>
python3 $LSP <root> symbols     <file>             # documentSymbol outline
python3 $LSP <root> wsymbols    <query>            # workspace/symbol search
```

Positions are **zero-based** line/character (LSP spec). `<file>` is relative to
`<root>` or absolute.

## Usage: library

The `scripts/` module lands on the boot `.pth`, so it is importable directly.

```python
import sys; sys.path.insert(0, "/mnt/skills/user/python-lsp/scripts")
from lsp_client import LSPClient

with LSPClient("/path/to/repo") as c:        # context manager reaps the subprocess
    c.open_all("pkg/service.py", "pkg/models.py")
    c.wait_for_index()                       # REQUIRED before querying — see below
    defs  = c.definition("pkg/service.py", 4, 8)   # -> [Location], follows imports
    refs  = c.references("pkg/models.py", 8, 4)     # -> [Location], binding-resolved
    typ   = c.hover("pkg/service.py", 4, 4)         # -> "(variable) u: User"
    diags = c.diagnostics("pkg/bad.py")             # -> [diagnostic dicts]
    outln = c.document_symbols("pkg/models.py")     # -> [SymbolInfo], file outline
    hits  = c.workspace_symbols("User")             # -> [SymbolInfo], project-wide
```

`Location` has `.path`, `.start_line`, `.start_char`, `.end_line`, `.end_char`
(all zero-based) and `.as_dict()`. Convert 1-based UI input with
`Position.from_one_based(line, col)`.

## Methods

| Method | Returns | Notes |
|---|---|---|
| `definition(file, line, col)` | `list[Location]` | Go-to-definition across files/imports. |
| `references(file, line, col)` | `list[Location]` | **Binding-resolved** — the win over ripgrep. Excludes same-named, unrelated symbols. |
| `hover(file, line, col)` | `str \| None` | Inferred type / signature string. |
| `diagnostics(file)` | `list[dict]` | pyright type/error diagnostics for the file. |
| `document_symbols(file)` | `list[SymbolInfo]` | One file's outline (classes/functions/methods); nesting via `.container`. |
| `workspace_symbols(query)` | `list[SymbolInfo]` | Project-wide fuzzy symbol search. Empty query = every symbol (expensive). |

`SymbolInfo` has `.name`, `.kind` (int), `.kind_name` (e.g. `"Class"`), `.location` (a `Location`), `.container`, and `.as_dict()`.

## The lifecycle gotchas (the parts that bite)

1. **Wait for indexing before querying.** Querying mid-index returns empty
   results — the most common silent failure. `wait_for_index()` blocks on
   pyright's `$/progress` begin/end cycle (with a diagnostics-arrival fallback).
   Always call it after `did_open` / `open_all` and before any query.
2. **Don't advertise `workspace.configuration` or `workspace.workspaceFolders`.**
   If the client claims either capability, pyright defers *all* analysis until
   the corresponding negotiation completes — the server starts its service
   instance and then goes silent (no diagnostics, no progress, queries hang).
   `start()` advertises neither, so pyright uses its defaults and analyzes open
   files immediately — no `didChangeConfiguration` nudge needed. Relevant if you
   reimplement the lifecycle or add capabilities. (Bisected against the fixture;
   `workspace.symbol` is safe to advertise.)
3. **Reap the subprocess.** Use the context manager (or call `stop()`) so
   sessions don't leak `pyright-langserver` processes. `stop()` sends
   `shutdown` + `exit`, then waits/terminates/kills as needed.
4. **Open the files you query.** Queries auto-`did_open` their target file, but
   for cross-file `references` open all relevant files first so pyright has
   built their models.

## Tests

```bash
cd /mnt/skills/user/python-lsp
python3 -m pytest tests/test_lsp_client.py -v
```

Round-trips against `tests/fixture/` (a small multi-file package): `definition`
follows an import, `references` excludes an unrelated same-named symbol, `hover`
returns an inferred type, `diagnostics` flags an intentional type error, the
indexing-wait is verified deterministic, and subprocess cleanup is checked for
orphans.
