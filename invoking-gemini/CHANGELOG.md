# invoking-gemini - Changelog

## 2026-07-21

### Added — audio (and video) input
- `image_path` now accepts **any** supported media file, not just images. Audio
  input verified working 2026-07-21 (3-beep WAV; `gemini-3.6-flash` returned the
  correct count and pitch direction). The param keeps its legacy name for
  back compat; docstrings now state what it really accepts.
- Explicit mimeType overrides for audio/video extensions `mimetypes` guesses
  wrongly or misses (.m4a/.aac/.flac/.ogg/.opus/.mp3/.wav/.aiff/.mp4/.mov/.webm/
  .heic/.heif). A wrong guess previously sent a bad mimeType and produced a
  confused answer rather than an error.
- New `MediaInputError` (subclass of `ValueError`) for deterministic input
  problems; retry loops re-raise it immediately instead of burning 3 attempts.
- 15MB inline cap enforced with an actionable message. Larger files need the
  Files API, which this client still does not implement.
- The direct google-generativeai SDK fallback now rejects non-image media with a
  clear message instead of an opaque PIL `UnidentifiedImageError`. Audio/video
  require the CF Gateway path.

**Routing note:** send audio to `gemini-3.6-flash`. `gemini-3.5-flash-lite` was
unreliable on the same clip — it reported three beeps then two on identical
input, and got the pitch direction wrong both times.

### ⚠️ BREAKING — `lite` alias repointed
- `MODEL_ALIASES['lite']`: `gemini-2.5-flash-lite` → `gemini-3.5-flash-lite`.
  Output cost goes from $0.40 to $2.50 per 1M (~6x) for any caller using
  `model="lite"`. Pin `gemini-2.5-flash-lite` by full ID if you need the old
  rate, though it is deprecated (below).
- The Gemini 2.5 **text** generation is retired from routing: `gemini-2.5-flash`,
  `gemini-2.5-flash-lite`, `gemini-2.5-pro`. Model IDs stay callable and the
  `stable-flash` / `stable-pro` aliases still resolve, so nothing hard-breaks,
  but they are no longer recommended targets. Image model `nano-banana`
  (gemini-2.5-flash-image) is NOT affected.
- Added `gemini-3.5-flash-lite` (GA 2026-07-21) as the cheap/bulk tier.

- Gemini 3.6 Flash (`gemini-3.6-flash`) reached GA (2026-07-21). Added it to
  the model registry and made it the new `DEFAULT_MODEL`.
- Repointed the `flash` alias from `gemini-3.5-flash` to `gemini-3.6-flash`.
  Added `flash-3.5` as a stable handle for the prior frontier Flash; `flash-3`
  still pins the older `gemini-3-flash-preview`.
- Rationale: 3.6 Flash is ~half Sonnet's cost (in $1.50 / out $7.50 vs ~$3 /
  ~$15) and improves coding/agentic quality with ~17% fewer output tokens than
  3.5 Flash — making it the default for sub-agent delegation.
- Updated SKILL.md and references/models.md tables (pricing, 64K output cap,
  benchmark deltas, tone-regression caveat).
- Not touched: `gemini-3.5-flash-lite` / `gemini-3.5-flash-cyber` (shipped same
  day) are not yet aliased; two helper fns still hardcode a
  `gemini-3-flash-preview` default in their signatures (pre-existing).

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

## [0.7.0] - 2026-07-23

### Other

- invoking-gemini: default to gemini-3.6-flash, retire Gemini 2.5 text models (#741)
- invoking-gemini: Nano Banana 2/Pro GA — keep -preview IDs on Developer API surface (#676)

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