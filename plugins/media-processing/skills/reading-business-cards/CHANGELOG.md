# reading-business-cards - Changelog

All notable changes to the `reading-business-cards` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.3.0] - 2026-10-07

### Changed

- `extract_cards.py` defaults to `claude-haiku-5-5` (was `claude-haiku-4-5`); docs use
  `claude-sonnet-5-5` for the escalation run. The Haiku-vs-Sonnet accuracy findings
  were measured on the 4.x models and have not been re-measured.
- `prep_cards.py` comments name tier families instead of 4.x generations (the floors
  are keyed by tier name, not model id).

### Fixed

- `temperature: 0` is only sent to legacy model families; Haiku 5.5 and Sonnet 5.5
  return HTTP 400 for it.
- `max_tokens` raised from 1500 to 4096 because adaptive thinking on 5.x models
  counts against it and could leave the JSON truncated.

## [2.2.0] - 2026-09-09

### Other

- prompt-audit: dated prompting patterns across the skill catalogue (#791)
- Deprecate mapping-codebases; adopt ruff 0.16.0 baseline (#747)

## [2.1.0] - 2026-06-16

### Other

- reading-business-cards: model-driven floor-based tile sizing (#700)

## [2.0.0] - 2026-06-16

### Other

- Add reading-business-cards skill (tiling + Haiku/Sonnet extraction)