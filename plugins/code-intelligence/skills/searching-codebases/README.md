# searching-codebases

Find code in any codebase by regex pattern or natural language concept. Auto-routes between n-gram indexed regex search (2-20x faster than ripgrep) and TF-IDF semantic search. Expands results to full functions via tree-sitting AST data. For Python sources, a binding-resolved reference/definition tier (pyright, via python-lsp) finds real callers and definitions without same-name false positives.

## Features

- **Dual search modes** — regex (pattern/identifier) and semantic (natural language concepts), auto-routed per query
- **N-gram indexed regex** — sparse inverted index narrows candidate files by 90-99% before ripgrep verification
- **TF-IDF semantic search** — cosine similarity ranking over code chunks (functions, classes)
- **Binding-resolved Python tier** — `--refs`/`--def`/`--hover` via pyright: true find-all-callers and go-to-definition that exclude same-named, unrelated symbols and follow imports. Engaged lazily; degrades to the regex text path when pyright/node is unavailable
- **AST context expansion** — `--expand` returns complete function/class bodies instead of line fragments
- **Flexible sources** — accepts GitHub URLs, local directories, uploaded files/archives, or project knowledge
- **Mixed queries** — multiple queries with different modes in a single invocation; indexes built once per mode

## Dependencies

- **ripgrep** — required for regex verification
- **tree-sitting** — auto-installs the bare `tree-sitter` package when needed: for `--expand` context and for the symbol→position resolution that seeds the binding-resolved tier (grammars ship bundled). Regex and semantic search work without it
- **scikit-learn** — required for semantic mode (auto-installs)
- **python-lsp** — provides the binding-resolved tier (`--refs`/`--def`/`--hover`); self-bootstraps pyright on first use and needs system `node` (v18+). Without it those flags degrade to the regex text path
