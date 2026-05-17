# container-layer - Changelog

All notable changes to the `container-layer` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
