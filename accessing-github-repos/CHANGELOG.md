# accessing-github-repos - Changelog

All notable changes to the `accessing-github-repos` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2.0.0] - 2026-01-06

### Added

- Rename git-in-containers to accessing-github-repos with credential-aware API

## [2.0.0] - 2026-01-06

### Changed

- **BREAKING**: Renamed skill from `git-in-containers` to `accessing-github-repos` (gerund naming convention)
- Complete rewrite with credential-aware API access
- Smart PAT detection from environment variables and project .env files
- Added comprehensive Python helper functions for GitHub API operations
- Added support for private repositories with authentication
- Added file push/update capabilities via GitHub API
- Expanded documentation with both Python and Bash examples

### Added

- Credential detection function (`get_github_auth()`)
- File fetching with automatic API/raw URL selection
- Repository tarball download support
- File create/update via GitHub API
- File SHA retrieval for updates
- Rate limiting documentation
- Capability matrix by auth level

## [1.0.0] - 2026-01-02

### Added

- Initial git-in-containers skill
- Basic raw.githubusercontent.com workarounds
- Directory tree fetching via GitHub API