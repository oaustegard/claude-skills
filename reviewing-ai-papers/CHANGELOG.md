# reviewing-ai-papers - Changelog

All notable changes to the `reviewing-ai-papers` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.4.0] - 2026-09-08

### Added

- "The ablation the paper did not run": a four-step check over the paper's own
  ablation tables, with a required output block, replacing the untooled
  "challenge novelty claims" guidance. Cites two diagnosed misses — SPD/hLLM
  (arXiv:2609.01807), whose decoder is never ablated and whose Hungarian solve
  is matched by a sort, and TTT-Embed (arXiv:2608.12569), whose residual query
  vector is never compared against label-free constructions of the same object.

## [0.3.0] - 2026-08-25

### Added

- add line numbers, markdown ToC, and other files listing
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Fixed

- limit markdown ToC to h1/h2 headings only

### Other

- top skills: separate by omission, and correct the guidance that said otherwise (#777)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
