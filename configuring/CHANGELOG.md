# configuring - Changelog

All notable changes to the `configuring` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.0.0] - 2026-01-22

### Changed

- **BREAKING**: Renamed skill from `getting-env` to `configuring` for Python import compatibility
- Updated all import examples to use `from configuring import ...`
- Expanded scope to cover environment variables, secrets, and other opinionated configuration setups

### Migration

Replace imports:
```python
# Old
from getting_env import get_env

# New
import sys
sys.path.insert(0, '/path/to/claude-skills')
from configuring import get_env
```

## [1.0.1] - 2026-01-22

### Added

- extend env loading for codex and turso

## [1.0.0] - 2026-01-22

### Added

- Add/Update skill: getting-env