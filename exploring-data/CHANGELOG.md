# exploring-data - Changelog

All notable changes to the `exploring-data` skill are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.1] - 2026-07-20

### Fixed

- `install_ydata.sh`: pin `setuptools<81`. ydata-profiling 4.18.x imports `pkg_resources`, removed in setuptools>=81; unpinned installs died on the first `ProfileReport` import with `ModuleNotFoundError: pkg_resources`.
- `install_ydata.sh`: add `pyarrow`. `analyze.sh` reads `.parquet` via pandas, which needs a parquet engine that wasn't installed.

### Added

- `scripts/visualize_findings.py`: render an EDA profile as a compact, self-contained Chart.js dashboard (missingness tiers, most-skewed/zero-inflated distributions, largest categorical breakdowns) instead of only linking the dense ydata HTML. Reads both ydata JSON and `profile_large.py --json` output. Stdlib-only.
- SKILL.md step A.5: present findings visually; prefer inline charts over a file link on surfaces that render visuals.

### Added

- add mapping-features skill for behavioral web app documentation (#432)
- add line numbers, markdown ToC, and other files listing
- add code maps and CLAUDE.md integration guidance
- Delete VERSION files, complete migration to frontmatter
- Migrate all 27 skills from VERSION files to frontmatter

### Fixed

- limit markdown ToC to h1/h2 headings only

### Other

- exploring-data v0.1.0: large-file profiling (DuckDB) + sketch ops (dups, overlap, drift) (#737)
- exploring-data: use absolute path for check_install.sh in Step 2 (#710)
- Remove _MAP.md files, direct agents to tree-sitting for code navigation (#545)
