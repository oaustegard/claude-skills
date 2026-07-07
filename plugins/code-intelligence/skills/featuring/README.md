# featuring

Generate hierarchical `_FEATURES.md` files that describe what a codebase **does** from a user/consumer perspective, anchored to source symbols via tree-sitting.

## Features

- **Top-down feature documentation** — organized by capability, not by file or directory structure
- **Hierarchical decomposition** — complex capability areas get their own sub-feature files with progressive disclosure
- **Multi-pass synthesis** — orientation scan, detailed extraction, then overview rewrite (written last, not first)
- **Symbol anchoring** — every feature references key symbols via `file#symbol` notation
- **Drift detection** — `check.py` validates all symbol references against the live codebase, catching renames, deletions, and uncovered new APIs
- **CI-ready** — check script returns exit codes suitable for GitHub Actions or pre-commit hooks

## Dependency

Requires the **tree-sitting** skill for AST-based code scanning.

## Relationship to Other Skills

- **tree-sitting** provides the structural inventory (what symbols exist)
- **featuring** adds the semantic layer (why they exist, what they accomplish together)
- **generating-lattice** offers stricter bidirectional traceability when needed
