# mapping-codebases - Changelog

All notable changes to the `mapping-codebases` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.7.0] - 2026-02-28

### Added

- TypeScript: full function/method signatures with parameters and return types (#234)
- TypeScript: `export default` function, class, and identifier declarations (#233)
- TypeScript: `export interface` and `export const/let` declarations
- Go: receiver method extraction nested under their types (#235)
- Go: function signatures with parameters and return types
- Rust: `impl` block method extraction nested under structs/enums (#235)
- Rust: function/method signatures with parameters and return types
- Ruby: methods nested under classes/modules instead of flat listing (#235)
- Ruby: `singleton_method` extraction (e.g., `self.format`)
- Ruby: method parameter signatures
- `--verbose` / `-v` flag for debug output (#236)

## [0.6.0] - 2026-02-03

### Added

- Add/Update skill: mapping-codebases
- Add 'interaction' memory type to remembering skill
