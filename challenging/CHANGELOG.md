# challenging - Changelog

All notable changes to the `challenging` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.5.0] - 2026-04-11

### Other

- challenging v0.5.0: prompt injection mitigation, credential path hardening, input size guard, retry logic, robust parsing

## [0.5.0] - 2026-04-11

### Security
- Prompt injection mitigation: artifact/context wrapped in XML tags with trust boundary instruction in all profile system prompts
- Removed `os.getcwd()` from credential search path — prevents rogue env files from redirecting API calls

### Added
- Input size guard: rejects artifacts > 500k chars before sending to API
- Retry with exponential backoff on transient API errors (429, 5xx, connection errors)

### Fixed
- System prompt extraction uses regex instead of fragile string slicing — handles code fences with language tags

## [0.4.0] - 2026-04-11

### Other

- challenging v0.4.0: fix Gemini model, token budget, defensive parsing

## [0.4.0] - 2026-04-10

### Fixed

- Gemini model upgraded from 2.5-pro to 3.1-pro-preview
- maxOutputTokens bumped 2048→16384 (thinking models exhaust budget on internal reasoning)
- Defensive response parsing in _invoke_gemini — handles missing `parts` key instead of crashing with KeyError
- Input validation for mode, adversary, and max_iterations parameters

## [0.3.0] - 2026-04-10

### Other

- challenging: generalize description, remove skill dependencies

## [0.2.0] - 2026-04-10

### Other

- challenging: proper progressive disclosure — one file per profile

## [0.1.0] - 2026-04-10

### Other

- Add challenging skill — adversarial review for deliverables