# invoking-gemini - Changelog

## 2026-05-28
- Nano Banana 2 (`gemini-3.1-flash-image-preview`) and Nano Banana Pro
  (`gemini-3-pro-image-preview`) reached GA on Vertex / Gemini Enterprise.
- Kept the `-preview` model IDs: the Gemini Developer API surface this client
  uses still serves both under `-preview` (GA IDs without the suffix are
  Vertex-only and 404 here). Verified against the live image-generation docs.
- Documented capabilities: 512/1K/2K GA + 4K preview, up to 14 reference
  images, Search + Image-Search grounding (3.1 Flash), thinking_level control.
- Noted video-as-input is a Vertex preview only; not available on the Developer API.


All notable changes to the `invoking-gemini` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.6.0] - 2026-05-23

### Added

- add Gemini 3.5 Flash + thinking_level, fix stale model docs (#669)

### Fixed

- retry on egress-proxy 503 ('DNS cache overflow') in remembering + invoking-gemini (#580)

### Other

- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)

## [0.5.0] - 2026-03-31

### Added

- surface Image Generation, add examples (#520)
- add mapping-features skill for behavioral web app documentation (#432)

### Other

- Regenerate _MAP.md files after @lat: backlink insertion (#504)
- Lattice v2: bidirectional source-anchored knowledge graph (#503)

## [0.3.1] - 2026-03-01

### Fixed

- use camelCase keys for Gemini REST API inline data

## [0.3.0] - 2026-03-01

### Added

- add image generation support + fix IMAGE_MODELS registry

## [0.3.0] - 2026-03-01

### Added

- `generate_image()` function for native image generation via Gemini image models
- `image` and `image-pro` model aliases for image generation
- `nano-banana` (gemini-2.5-flash-image) to IMAGE_MODELS registry
- Image generation documentation in SKILL.md with prompt patterns and examples

### Fixed

- IMAGE_MODELS registry now maps display names to actual API model IDs
  (was mapping names to themselves, causing 404 errors)
- `nano-banana-2` → `gemini-3.1-flash-image-preview`
- `nano-banana-pro` → `gemini-3-pro-image-preview`
- `nano-banana` → `gemini-2.5-flash-image`

## [0.2.0] - 2026-03-01

### Added

- update invoking-gemini model registry to current Gemini lineup

## [0.1.0] - 2026-03-01

### Added

- route invoking-gemini through Cloudflare AI Gateway
- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Changed

- migrate API credential management to project knowledge files

### Fixed

- limit markdown ToC to h1/h2 headings only