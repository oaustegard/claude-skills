# Changelog

## 0.6.0

Changed from 0.5.0:

### Deleted
- Per-zone image-to-svg calls (4 pipeline runs)
- Per-zone smoothing (kuwahara, oilpaint per zone)
- ClipPath compositing
- Opaque crop + translate trick
- Multi-pass segmentation (21 IM transforms × MP segmenter)
- MediaPipe selfie segmenter dependency

### Kept
- Agent annotation API (focus_targets, focus_edges with bboxes)
- MediaPipe face landmarks for precise face ovals
- Four-zone concept (target / edge / periphery / background)

### Added
- Single-pass pipeline with unified palette
- Zone-aware contour simplification (epsilon + min_area per zone)
- Per-zone style transforms (desaturate, mute, warm/cool, opacity)
- Automatic periphery generation (dilated foreground buffer)
- Zone-tagged shapes in SVG output (<g> groups)

## [0.7.0] - 2026-09-09

### Added

- svg-portrait-mode v0.5.0 — foveated vectorization (#489)

### Fixed

- repair broken frontmatter, mark obsolete skills, close registry gaps (#746)

### Other

- prompt-audit: dated prompting patterns across the skill catalogue (#791)
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
- Fix inter-zone tearing by unifying epsilon across zones (#512) (#513)
- Regenerate _MAP.md files after @lat: backlink insertion (#504)
- Lattice v2: bidirectional source-anchored knowledge graph (#503)
- svg-portrait-mode v0.6.0: Selective simplification (#491)
- svg-portrait-mode v0.3.0: Complete rewrite using image-to-svg pipeline
- svg-portrait-mode v0.2.0: Add MediaPipe integration
- Add svg-portrait-mode skill v0.1.0
