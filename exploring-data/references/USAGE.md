# Exploring Data - Usage Documentation

## What This Skill Does

Generates comprehensive exploratory data analysis reports using ydata-profiling, a battle-tested library with 12.5k+ GitHub stars.

## Features

**Minimal Mode (default, 5-10s):**
- Dataset overview (rows, columns, types, memory)
- Variable analysis (distributions, statistics)
- Missing value analysis
- Duplicate detection
- Correlation matrices
- Data quality alerts

**Full Mode (10-20s):**
- Everything in minimal +
- Scatter plot matrices
- Sample data display
- Character/script analysis (for text)
- Auto-correlation
- More sophisticated visualizations

## Output Formats

**HTML (default):**
- Interactive, self-contained report (500KB-2MB)
- Tabbed navigation
- Embedded visualizations
- Downloadable via browser

**JSON:**
- Machine-readable format
- For programmatic access
- Can be parsed by other tools

## Installation

**First use only (~19s):**
```bash
bash /mnt/skills/user/exploring-data/scripts/install_ydata.sh
```

Creates isolated venv at `/home/claude/.venvs/exploring-data` with:
- ydata-profiling 4.17.0
- ~50 dependencies
- Total: 559MB

**Subsequent uses:** Instant (venv already exists)

## Performance

| Dataset Size | Minimal Mode | Full Mode |
|-------------|-------------|-----------|
| <10k rows | 2-5s | 5-10s |
| 10-50k rows | 5-10s | 10-15s |
| 50-100k rows | 10-15s | 15-25s |

## Troubleshooting

**If installation fails:**
- Check network access to pypi.org
- Ensure uv is available: `uv --version`
- Try manual install:
  ```bash
  uv venv /home/claude/.venvs/exploring-data
  uv pip install ydata-profiling setuptools --python /home/claude/.venvs/exploring-data
  ```

**If analysis fails:**
- Check file format is supported (.csv, .xlsx, .json, .parquet, .tsv)
- Verify file exists at specified path
- Check file is not corrupted
