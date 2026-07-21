---
name: exploring-data
description: Exploratory data analysis. Use when users upload .csv/.xlsx/.json/.parquet files or request "explore data", "analyze dataset", "EDA", "profile data". Small files get ydata-profiling HTML/JSON reports; large files (>200MB or >5M rows) get fixed-memory DuckDB/sketch profiling. Also covers near-duplicate row detection, cross-file key overlap ("can these join?"), dataset drift vs a stored baseline, and time-series profiling.
metadata:
  version: 0.1.1
---

# Exploring Data

## 0. Route by size FIRST

```bash
ls -la <filepath>   # or: wc -l for row estimate
```

- **< 200MB and < ~5M rows** → ydata-profiling path (section A). Exact stats, interactive HTML.
- **Larger** → large-file path (section B). ydata-profiling loads everything into pandas and will crawl or OOM; the DuckDB/sketch path runs in fixed memory at any size.
- **Task-specific ops** (any size): duplicates, join feasibility, drift → section C.

## A. Standard path (ydata-profiling)

### 1. Check if installed (instant)
```bash
bash /mnt/skills/user/exploring-data/scripts/check_install.sh
```
Returns: `installed` or `not_installed`

### 2. Install if needed (one-time, ~19s)
```bash
if [ "$(bash /mnt/skills/user/exploring-data/scripts/check_install.sh)" = "not_installed" ]; then
    bash /mnt/skills/user/exploring-data/scripts/install_ydata.sh
fi
```

### 3. Run analysis (always generates JSON + HTML by default)
```bash
bash /mnt/skills/user/exploring-data/scripts/analyze.sh <filepath> [minimal|full] [html|json]
```

**Defaults:** minimal + html (also generates JSON)

**Output:**
- `eda_report.html` - Interactive report for user
- `eda_report.json` - Machine-readable for Claude analysis

### 4. If Claude needs to analyze (user asks "what do you think?" etc.)
```bash
python /mnt/skills/user/exploring-data/scripts/summarize_insights.py /mnt/user-data/outputs/eda_report.json
```

Claude should read the stdout markdown summary, NOT the full JSON report.

### 5. Present findings visually (don't just hand over the ydata HTML)

The ydata report is exhaustive but dense; a link to it is a weak deliverable.
Turn the JSON into a compact dashboard of the findings that matter:
```bash
python3 /mnt/skills/user/exploring-data/scripts/visualize_findings.py \
    /mnt/user-data/outputs/eda_report.json
# → /mnt/user-data/outputs/eda_findings.html
```
Emits a single self-contained HTML file (Chart.js from cdnjs, dark-mode aware):
missingness by column (tiered good/bad), the most skewed or zero-inflated
numeric distributions as small-multiple histograms, and the largest categorical
breakdowns. `--top N` caps charts per category (default 6). Also reads
`profile_large.py --json` output, so the large-file path gets the same treatment.

Present BOTH files: `eda_findings.html` for the headline read, `eda_report.html`
for the full drill-down. In a chat surface that renders inline visuals, prefer
rendering the two or three findings that actually answer the user's question as
inline charts over linking a file — a link the user has to open is the weakest
form of "showing" data.

### Modes

**Minimal (default, 5-10s):** overview, variable analysis, correlations, missing values, alerts
**Full (10-20s):** minimal + scatter matrices, sample data, character analysis

Full-mode triggers: "comprehensive analysis", "detailed EDA", "full profiling", "deep analysis". Otherwise minimal.

### Time series
If the data has a datetime index/column and the user cares about temporal behavior
(gaps, trends, seasonality, autocorrelation), pass `tsmode=True` to ProfileReport —
run the venv python directly instead of analyze.sh:
```python
ProfileReport(df, tsmode=True, sortby="<datetime_col>", title=...)
```
This adds gap detection, stationarity and seasonality checks that the default
report omits.

### Small-file drift
Comparing two versions of a dataset that BOTH fit in memory: use ydata's native
compare — `ProfileReport(df_a).compare(ProfileReport(df_b)).to_file(...)`.
For files too big to load, or comparing against a months-old file you no longer
have, use the sketch snapshot/drift ops in section C.

## B. Large-file path (DuckDB, fixed memory)

### 1. Install deps (idempotent, ~10s first time)
```bash
bash /mnt/skills/user/exploring-data/scripts/install_large.sh
```

### 2. Profile
```bash
python3 /mnt/skills/user/exploring-data/scripts/profile_large.py <file> [--json out.json]
```

Streams the file through DuckDB: per-column null%, approximate distinct counts
(HLL), min/max/mean, approximate quantiles (t-digest) for numerics, top-5
values for strings, plus quality flags (mostly-null, constant, id-like
columns). Markdown lands on stdout — read it directly, no summarize step
needed. Handles csv/tsv/parquet/json/ndjson. 1M rows profiles in seconds;
memory is flat regardless of file size.

For ad-hoc follow-up queries on the same large file, use DuckDB SQL directly
(`duckdb.connect().execute("SELECT ... FROM read_csv_auto('...')")`) rather
than loading pandas.

## C. Sketch ops (any file size, fixed memory)

All via `scripts/sketch_ops.py` (deps from install_large.sh). These answer
questions profilers don't:

### Near-duplicate rows
```bash
python3 sketch_ops.py dups <file> [--threshold 0.9] [--cols a,b,c]
```
Exact duplicates counted by hash; near-duplicates via MinHash LSH over row
tokens. Use `--cols` to restrict to the columns that define identity.

### Key overlap / join feasibility
```bash
python3 sketch_ops.py overlap <fileA> <fileB> --key <col> [--key-b <col>]
```
Theta sketches per key column → estimated intersection, Jaccard, and "% of A's
keys in B" both ways — answers "will this join hold?" without loading either
file.

### Drift vs stored baseline
```bash
python3 sketch_ops.py snapshot <file> --out baseline.sketch.json   # ~20KB
python3 sketch_ops.py drift <newfile> --baseline baseline.sketch.json
```
Snapshot serializes HLL (all columns) + KLL quantile sketches (numeric
columns) to a small JSON. Drift reports schema changes, >10% shifts in
distinct counts, and IQR-relative quantile movement. The snapshot is a few KB
— store it (repo, memory) and diff next month's delivery against it without
keeping the original file.

Note: snapshot/dups stream rows through Python (~1M rows in a few seconds);
profile_large is pure DuckDB and faster. For a quick look at a big file,
profile first, sketch ops only when the question calls for them.
