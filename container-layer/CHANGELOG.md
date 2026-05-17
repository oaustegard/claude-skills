# container-layer - Changelog

All notable changes to the `container-layer` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.2] - 2026-05-17

### Fixed

- `PYTHON_INSTALL_PATHS` now includes `/usr/bin`, `/usr/lib`, `/usr/share` so
  apt-install layers get the diff-vs-baseline treatment instead of whole-tree
  capture. `_exec_run` already auto-adds these three paths to `snapshot_paths`
  when it sees `apt-get install`, but before this fix they weren't baselined,
  so any layer with `apt-get install <one tiny package>` ballooned by ~600MB
  compressed (the full `/usr/{bin,lib,share}` trees). Verified empirically
  against the libfuse2 install in oaustegard/claude-workspace-fuse: layer
  jumped from 940MB → 1625MB compressed. Closes oaustegard/claude-skills#652.

### Notes

- Despite the name, `PYTHON_INSTALL_PATHS` is no longer python-only. Kept the
  name for backwards compatibility with any external importer; consider
  renaming to `BASELINED_PATHS` in a future major bump.
- `snapshot_baseline()` walks these dirs at build-time. `/usr/lib` is the
  largest (~2GB raw) — adds a few seconds to baseline capture. Acceptable
  for build-time; negligible vs. the layer-restore time it saves.

## [0.2.1] - 2026-05-17

### Other

- container-layer v0.2.1: cover python3.10-3.13 dist-packages in baseline (#651)

## [0.2.1] - 2026-05-17

### Fixed

- `PYTHON_INSTALL_PATHS` now lists python3.10 through python3.13 dist-packages
  instead of only python3.12. The previous single entry missed containers using
  3.11 (which is most of them), causing the diff-vs-baseline logic in
  `_dedup_paths` to silently fall through to whole-tree snapshot — every layer
  captured all of dist-packages instead of just newly-installed files.
  Empirically verified against oaustegard/claude-workspace-fuse: cached "slim"
  layer was 678MB compressed with 712M torch + 944M modular still embedded.

### Added

- Regression tests in `scripts/test_baseline_paths.py` lock in the new coverage
  and assert the diff path is taken when a SNAPSHOT directive references a
  baselined dir.

## [0.2.0] - 2026-05-17

### Added

- add ISO date prefix to layer release names for sortability (#535)

### Other

- container-layer v0.2.0: named layers + compose (#650)
- container-layer: stop leaking GH_TOKEN via subprocess TimeoutExpired (#596)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
- marketplace: restructure as category-based plugins for Claude Code discovery (#530)
- container-layer: add README
- container-layer: update boot-ccotw.sh (fix function ordering, abs paths)
- container-layer: update scripts/cli.py
- container-layer: update scripts/containerfile.py
- container-layer: add boot.sh
- container-layer: add Containerfile

## [0.2.0] - 2026-05-17

### Added

- Named layers: `ContainerLayer(..., layer_name="X")` produces cache release tag
  `layer-X-<hash>` instead of `layer-<hash>`. Enables per-name cache retention
  policies and multi-layer composition without collisions.
- `default_layer_name(path)`: derives layer name from filename
  (`Containerfile` → `base`, `Containerfile.mojo` → `mojo`, etc.).
- `compose(containerfile_paths, ...)`: orchestrates sequential restore (or
  build+push on miss) of multiple named layers. Mirrors Docker's additive-overlay
  semantics — later layers can overwrite earlier ones' files.
- CLI `compose` subcommand for the same.
- `--name` flag on `build` / `restore` / `hash` / `inspect` subcommands for
  single-layer naming.

### Backwards compatibility

- Unnamed layers (no `layer_name`, no `--name`) keep the old `layer-<hash>` tag.
  Existing single-Containerfile callers see no cache invalidation.
- Existing `build_and_push()` / `restore_or_build()` / `build_only()` methods
  unchanged.

## [0.1.0] - 2026-04-04

### Other

- Add container-layer skill