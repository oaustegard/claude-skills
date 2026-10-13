# swarming-failing-tests - Changelog

All notable changes to the `swarming-failing-tests` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2026-10-13

### Other

- swarming-failing-tests 0.2.0, dispatching-subagents 0.2.0: worker deny rules, one_stage_ok

## [0.2.0] - 2026-10-13

### Other

- swarming-failing-tests 0.2.0: `worker.deny` (claude --disallowedTools) and `tests.one_stage_ok`, from the swarm-decomp run

## [0.1.6] - 2026-10-13

### Other

- swarming-failing-tests 0.1.6: catalogue item 51 (a suite outside every partition is never re-measured)

## [0.1.5] - 2026-10-13

### Other

- swarming-failing-tests 0.1.5: 'stale' worker status; fan out the final measurement

## [0.1.4] - 2026-10-12

### Other

- swarming-failing-tests 0.1.4: full refresh when the queue drains with unrefreshed merges

## [0.1.3] - 2026-10-12

### Other

- swarming-failing-tests 0.1.3: federation state commit chains onto the fetched remote tip

## [0.1.2] - 2026-10-12

### Other

- swarming-failing-tests 0.1.2: tiered quick refresh (quick suites every 25 merges, bisect only over those merges)

## [0.1.1] - 2026-10-12

### Other

- swarming-failing-tests 0.1.1: reap deletes Claude Code's per-worker temp dir (a runaway worker's task output reached 4.3 GB)

## [0.1.0] - 2026-10-12

### Other

- swarming-failing-tests: the haiku-cc swarm harness as a reusable skill