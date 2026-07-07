# muninn-boot - Changelog

All notable changes to the `muninn-boot` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.1.0] - 2026-07-09

### Added

- Warm-container fast path: sentinel `/home/claude/.muninn-booted` (content = pinned SHAs, written only on successful boot) lets re-invocations exit in ~0s. Motivation: the project instruction is reinjected with every message, forcing a per-turn "is this a new conversation?" judgment that resolved toward wasteful re-boots; the sentinel removes the judgment. Skinny boot bypasses the fast path.
- Repo home: the skill now lives canonically at claude-skills/muninn-boot/ (previously the project upload was the only copy).

### Fixed

- The claude-skills fetch now excludes the relocated `remembering/` stub so a boot can never overwrite a project-uploaded remembering skill at /mnt/skills/user/remembering.

## [1.0.0] - prior

- Pinned two-repo fetch, env sourcing, .pth setup, boot() run. (Existed only as a project upload.)
