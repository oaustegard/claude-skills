# Changelog

## 0.4.0 (2026-08-22)

### Fixed: gather.py crashed on the second run against a repo
tree-sitting's `/tmp/treesit-cache` persists symbols and imports but not file
source, so every cache HIT returned `entry.source = None`. `identify_key_files`
(`len(entry.source)`) and the Key Source Excerpts emitter
(`entry.source.decode(...)`) both used it unguarded. A cold run succeeded and
wrote the cache; the next run with the same repo + skip set exited 1 with a
TypeError, which read as flakiness. `_source_bytes()` now falls back to reading
the file from disk. Verified cold/warm output is byte-identical.

### New: `--orient`
Emits the orientation header only — complexity assessment, decomposition
ranking, directory tree, entry points — and stops before the symbol inventory.
~115 lines against 5,697 for the full output on a 71k-line repo. Use it whenever
the deliverable is your own understanding rather than a written `_FEATURES.md`.
The full mode now prints its own line count first when the output exceeds 400
lines, so the cost of not using `--orient` is visible before the scroll.

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

## [0.4.0] - 2026-08-22

### Other

- featuring: fix source=None crash on cache hit, add --orient (#770)
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)

## [0.3.0] - 2026-04-08

### Added

- add treesit.py CLI, fix cross-process cache loss, fix Symbol dict bug (#536)

### Other

- marketplace: restructure as category-based plugins for Claude Code discovery (#530)
- Add missing READMEs for searching-codebases, featuring, tree-sitting (#521)

## [0.2.0] - 2026-03-31

### Added

- v0.2.0 — Hierarchical features + multi-pass synthesis (#515)