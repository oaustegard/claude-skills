# invoking-gemini - Changelog

All notable changes to the `invoking-gemini` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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