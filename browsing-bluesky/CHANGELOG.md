# browsing-bluesky - Changelog

All notable changes to the `browsing-bluesky` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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