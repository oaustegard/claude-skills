# exploring-codebases
Inspired by [[2601.23254] GrepRAG: An Empirical Study and Optimization of Grep-Like Retrieval for Code Completion](https://arxiv.org/abs/2601.23254) and my previous [mapping-codebases](https://github.com/oaustegard/claude-skills/tree/main/mapping-codebases)
Semantic search for codebases. Locates matches with ripgrep and expands them into full AST nodes (functions/classes) using tree-sitter. Returns complete, syntactically valid code blocks rather than fragmented lines. Use when looking for specific implementations, examples, or references where full context is needed.
