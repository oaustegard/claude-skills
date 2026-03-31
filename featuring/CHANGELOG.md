# Changelog

## 0.2.0 (2026-03-31)

### Hierarchical features support
- Root `_FEATURES.md` can link to sub-feature files for complex capability areas
- Sub-files follow the same format recursively, with back-links to parent
- Hierarchy is feature/capability driven, not folder driven

### Multi-pass synthesis
- Pass 1: Orientation scan → form hypothesis about what codebase does
- Pass 2: Detailed feature extraction, per-capability hierarchy decisions
- Pass 3: Overview rewrite with progressive disclosure (written LAST, not first)

### gather.py
- New `--area` flag for focused sub-directory scanning
- New "Complexity Assessment" section in output with hierarchy recommendation
- `compute_complexity()` function identifies decomposition candidates by symbol density

### check.py
- Discovers and validates full _FEATURES.md hierarchy (root + all linked sub-files)
- Detects orphan _FEATURES.md files not linked from any parent
- Detects broken sub-file links
- Reports now show which source file contains broken refs

### Examples
- Split example into root (_FEATURES_example_root.md) and sub-file (_FEATURES_example_sub.md)
- Demonstrates progressive disclosure: root has summaries + links, sub-file has full detail

## 0.1.0 (2026-03-29)

Initial release.
- gather.py: AST-based structural scanning via tree-sitting
- check.py: drift detection (broken refs, dead features, uncovered symbols)
- Single flat _FEATURES.md format
- CI integration example

## [0.2.0] - 2026-03-31

### Added

- v0.2.0 — Hierarchical features + multi-pass synthesis (#515)
