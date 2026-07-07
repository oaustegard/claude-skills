# optimizing-skills - Changelog

All notable changes to the `optimizing-skills` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-05-29

### Other

- optimizing-skills v0.2.0: per-criterion gate scoring + author-sample requirement (#679)

## [0.2.0] - 2026-05-29

### Changed

- Gate scoring is now **per-criterion**; accept/reject is decided by the
  triggering-failure criterion, with other criteria as regression guards.
  A collapsed pass/fail masked a 60%→0% win behind an unrelated 0/5 tie and
  would have rejected a real improvement (validated retroactively against the
  down-skilling v1.2.0 edit — see claude-workspace
  `experiments/optimizing-skills-retro/`).

### Added

- Require **≥2 author samples per version** (or a fixed author across arms)
  when the skill's artifact is compiled by an Agent (down-skilling,
  creating-skill), to separate edit effect from author variance. The same
  down-skilling edit measured 95%→0% with one author pair and 60%→0% with
  another.

## [0.1.0] - 2026-05-29

### Other

- Add optimizing-skills: validation-gated skill-revision discipline (#677)