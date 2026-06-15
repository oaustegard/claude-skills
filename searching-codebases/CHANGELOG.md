# searching-codebases - Changelog

All notable changes to the `searching-codebases` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.1.0] - 2026-06-15

### Added

- add treesit.py CLI, fix cross-process cache loss, fix Symbol dict bug (#536)

### Other

- searching-codebases: binding-resolved Python tier via python-lsp (#695) (#697)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
- Add missing READMEs for searching-codebases, featuring, tree-sitting (#521)

## [2.1.0] - 2026-06-15

### Added

- Binding-resolved reference/definition tier for Python via the `python-lsp` skill (pyright): `--refs`, `--def`, `--hover` (#695)
  - `--refs SYMBOL` excludes same-named-but-unrelated symbols and follows imports — the precision the regex cross-reference tier lacks
  - Engaged lazily (pyright index cost paid only on these flags); Python-only with a mandatory soft fallback to the regex text path (non-`.py`, or pyright/node absent) that emits a one-line degradation note
  - `scripts/lsp_refs.py`: tree-sitting symbol→position resolution, 1-based↔0-based conversion at the LSP boundary, lifecycle-safe queries (index-wait + subprocess reaping)
  - `tests/test_lsp_refs.py`: binding-resolution, import-following, indexing-wait determinism, no orphaned subprocess, and soft-fallback coverage

## [2.0.0] - 2026-03-31

### Other

- exploring v1.0.0, searching v2.0.0: tree-sitting replaces mapping-codebases
- Regenerate _MAP.md files after @lat: backlink insertion (#504)
- Lattice v2: bidirectional source-anchored knowledge graph (#503)

## [1.0.0] - 2026-03-25

### Added

- add mapping-features skill for behavioral web app documentation (#432)

### Other

- Remove searching-codebases/scripts/_MAP.md (absorbed into search.py)
- Remove searching-codebases/scripts/flowing.py (absorbed into search.py)
- Remove searching-codebases/scripts/pipeline.py (absorbed into search.py)
- searching-codebases/scripts/sparse_ngrams.py
- searching-codebases/scripts/ngram_index.py
- searching-codebases/scripts/context.py
- searching-codebases/scripts/resolve.py
- searching-codebases/scripts/search.py
- searching-codebases/SKILL.md
- Implement #414, #415, #416: perch findings digests, boot flight awareness, inline links
- Add searching-codebases skill