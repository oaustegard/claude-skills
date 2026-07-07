# llm-as-computer - Changelog

All notable changes to the `llm-as-computer` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.1] - 2026-03-25

### Other

- llm-as-computer: raise step limits, add --max-steps and --quiet CLI flags (#465)

## [1.0.1] - 2026-03-25

### Changed

- executor.mojo: raise default max_steps from 50K to 5M
- executor.mojo: add `--max-steps N` CLI flag for runtime override
- executor.mojo: add `--quiet` flag to suppress per-step trace output
- runner.py: raise all default max_steps to 5M
- runner.py: pass `--max-steps` through to Mojo binary
- runner.py: scale subprocess timeout with step count

## [1.0.0] - 2026-03-25

### Other

- Add llm-as-computer skill: src/setup.sh
- Add llm-as-computer skill: src/executor.mojo
- Add llm-as-computer skill: src/runner.py
- Add llm-as-computer skill: src/programs.py
- Add llm-as-computer skill: src/isa_lite.py
- Add llm-as-computer skill: SKILL.md