## 0.6.0 — 2026-08-28

- Authentication prefers `MUNINN_BSKY_HANDLE` / `MUNINN_BSKY_APP_PASSWORD`,
  falling back to the unprefixed pair only when no Muninn pair is set. A booted
  container holds both, and reading the unprefixed one first meant every
  authenticated read silently came back as the account owner.
- `BSKY_IDENTITY=muninn|owner` selects one pair outright; a named pair that is
  absent reads as public rather than substituting the other. An unrecognised
  value raises.
- `authenticated_identity()` reports which pair answered, alongside the handle
  and DID. `get_authenticated_user()` is unchanged.
- `__init__.py` falls back to a by-path load when exec'd without a parent
  package, which is what pytest's collector does to a hyphenated skill
  directory. First tests for the skill: 12, offline.

# browsing-bluesky - Changelog

All notable changes to the `browsing-bluesky` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.6.0] - 2026-08-30

### Added

- image transcription via Gemini Lite/Flash/3.5-Flash or Anthropic Haiku/Opus (#668)
- add mapping-features skill for behavioral web app documentation (#432)
- v5.1.0 — partial IDs, curation, episodic scoring, decision traces, FTS5 improvements

### Other

- atprotoing 0.3.0 and browsing-bluesky 0.6.0 (#778)
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
- Regenerate _MAP.md files after @lat: backlink insertion (#504)
- Lattice v2: bidirectional source-anchored knowledge graph (#503)

## [0.5.1] - 2026-02-28

### Fixed

- document actual sample_firehose() return format and add missing bsky utility exports

### Other

- Add fetch_all parameter to recall() for comprehensive memory retrieval

## [0.5.0] - 2026-02-08

### Added

- add trending API and fix NODE_PATH resolution (#271, #272)

## [0.5.0] - 2026-02-08

### Added

- Add `get_trending()` for rich trend data with post counts, status, category, and actors (#272)
- Add `get_trending_topics()` for lightweight trending topic scan (#272)
- Restructure zeitgeist workflow: trending API first, firehose as deep-dive tool (#272)

### Fixed

- Fix NODE_PATH resolution in zeitgeist-sample.js so modules resolve regardless of working directory (#271)

## [0.4.1] - 2026-02-06

### Added

- Add type-safe MemoryResult and proactive recall_hints (#211, #212)

### Fixed

- add facet URL parsing and image alt text to _parse_post()

## [0.4.0] - 2026-01-25

### Added

- Consolidate account categorization from categorizing-bsky-accounts

### Changed

- Improve code consistency in account analysis

## [0.4.0] - 2026-01-25

### Added

- Consolidate account analysis from categorizing-bsky-accounts skill
- Add `analyze_accounts()` for batch account analysis with keyword extraction
- Add `analyze_account()` for single account analysis
- Add `get_all_following()` and `get_all_followers()` with pagination support
- Add `extract_keywords()` for YAKE-based keyword extraction
- Add `extract_post_text()` helper for post text concatenation
- Support domain-specific stopwords (en, ai, ls) for keyword filtering
- Support exclude patterns for filtering out bot/spam accounts

## [0.3.0] - 2026-01-25

### Added

- Add optional authentication for personalized feeds
- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance

### Fixed

- Route authenticated requests to PDS endpoint
- limit markdown ToC to h1/h2 headings only

## [0.2.0] - 2026-01-01

### Added

- Enhance browsing-bluesky with engagement and social graph features

### Other

- Update SKILL.md

## [0.1.0] - 2026-01-01

### Added

- Consolidate firehose sampling into browsing-bluesky
- Add browsing-bluesky skill and update remembering docs

### Fixed

- Move version to metadata wrapper in browsing-bluesky