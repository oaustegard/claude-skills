# optimizing-skills - Changelog

All notable changes to the `optimizing-skills` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.3.0] - 2026-09-05

### Added

- **Ledger step.** Every revision now runs `skill_ledger.py check` before
  scoring and `skill_ledger.py record` after the gate decides, rejections
  included. Previously a rejected candidate was discarded with nothing written
  down, so a later session with no view of this one could propose the same edit
  and pay to score it again. Imported from WikiSkill's `skill-impact.md`
  (arXiv:2608.27454); the script lives in claude-workspace
  (`scripts/skill_ledger.py`) and computes the diff itself rather than
  accepting one from the proposing model.

### Changed

- **Gate step 3 isolates the scoring agent.** It receives the skill version and
  the check task only, never the ledger, the revision notes, or the diagnosis
  behind the edit. WikiSkill ablated this and measured final quality falling
  from 63.7 to 60.9 on average, and 72.6 to 64.8 on their hardest split, when
  the worker could read the improver's knowledge store.
- **`remember()` is now scoped to judgment.** The ledger carries the diffs and
  their scores; the memory carries what was learned about editing this
  particular skill.

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