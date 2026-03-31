# searching-codebases

Find code in any codebase by regex pattern or natural language concept. Auto-routes between n-gram indexed regex search (2-20x faster than ripgrep) and TF-IDF semantic search. Expands results to full functions via tree-sitting AST data.

## Features

- **Dual search modes** — regex (pattern/identifier) and semantic (natural language concepts), auto-routed per query
- **N-gram indexed regex** — sparse inverted index narrows candidate files by 90-99% before ripgrep verification
- **TF-IDF semantic search** — cosine similarity ranking over code chunks (functions, classes)
- **AST context expansion** — optional tree-sitting integration returns complete function/class bodies instead of line fragments
- **Flexible sources** — accepts GitHub URLs, local directories, uploaded files/archives, or project knowledge
- **Mixed queries** — multiple queries with different modes in a single invocation; indexes built once per mode

## Dependencies

- **ripgrep** — required for regex verification
- **tree-sitting** — optional, enables `--expand` for structural context
- **scikit-learn** — required for semantic mode (auto-installs)
