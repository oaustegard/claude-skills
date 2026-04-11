# challenging - Changelog

All notable changes to the `challenging` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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