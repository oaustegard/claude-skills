# assessing-impact

Pre-change blast-radius reports for a symbol or file in a local codebase. Walks the `tree-sitting` AST cache for direct references, augments with a plain-text scan over file types tree-sitting doesn't parse, and clusters affected sites by package, tests, docs, and (when present) `_FEATURES.md` features.

## Features

- **Symbol or file targets** — identify what breaks if you change `validateUser` or refactor `auth.py`
- **AST-aware ref discovery** — uses tree-sitting's parsed corpus, excluding definition lines so refs are uses, not declarations
- **Non-AST text scan** — picks up `Dockerfile`, `.ini`, `.env`, `.properties`, plain `.txt`/`.rst` references that the AST scanner misses
- **Three-axis clustering** — code-by-package, tests, and docs, with optional `_FEATURES.md` overlay
- **Test surface suggestion** — surfaces tests that already reference the target plus tests neighboring the definition
- **No opinionated risk score** — structured report is input for the LLM that writes the final summary
- **Substring-fallback warning** — flags when the target had no exact match so the resulting noise is visible
- **Markdown or JSON output**

## Dependency

Requires the **tree-sitting** skill — imports `engine.py` directly and uses its bundled grammars.

## Relationship to Other Skills

- **exploring-codebases** — divergent first-encounter EDA; run before `assessing-impact` if the repo also needs an `_FEATURES.md`
- **searching-codebases** — convergent "where is X" search; complementary, not a replacement for impact analysis
- **tree-sitting** — drill into specific call sites once impact has identified them
- **featuring** — produces the `_FEATURES.md` files that `assessing-impact` overlays for feature-area clustering

## Honest Limits

Text-based ref discovery, no type/MRO resolution, no cross-language or cross-repo tracing, no persistent index. For deep ongoing impact analysis on a daily codebase, GitNexus or SourceGraph remain the right tool. This skill is for the ad-hoc case: *"I'm about to refactor X in a repo I don't own, what should I be careful about?"*
