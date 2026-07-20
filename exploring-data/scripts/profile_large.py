#!/usr/bin/env python3
"""Out-of-core profiling for files too large for ydata-profiling.

Uses DuckDB streaming scans: approx_count_distinct (HLL) and approx_quantile
(t-digest) run in fixed memory regardless of file size.

Usage: profile_large.py <datafile> [--json /path/out.json]
Output: markdown summary to stdout (Claude reads this directly).
"""
import json
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    sys.exit("duckdb not installed — run install_large.sh first")


def reader_sql(path: Path) -> str:
    s = path.suffix.lower()
    p = str(path).replace("'", "''")
    if s in (".csv", ".tsv", ".txt"):
        return f"read_csv_auto('{p}', sample_size=-1)"
    if s == ".parquet":
        return f"read_parquet('{p}')"
    if s in (".json", ".ndjson", ".jsonl"):
        return f"read_json_auto('{p}')"
    sys.exit(f"Unsupported format: {s}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    if not path.is_file():
        sys.exit(f"File not found: {path}")
    json_out = None
    if "--json" in sys.argv:
        json_out = Path(sys.argv[sys.argv.index("--json") + 1])

    con = duckdb.connect()
    src = reader_sql(path)
    cols = con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()
    n_rows = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]

    numeric_types = ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
                     "FLOAT", "DOUBLE", "DECIMAL", "UTINYINT", "USMALLINT",
                     "UINTEGER", "UBIGINT")
    report = {"file": str(path), "rows": n_rows,
              "size_bytes": path.stat().st_size, "columns": []}

    for name, dtype, *_ in cols:
        q = f'"{name}"'
        base = con.execute(
            f"SELECT count({q}), approx_count_distinct({q}) FROM {src}"
        ).fetchone()
        non_null, distinct = base
        col = {"name": name, "dtype": dtype,
               "null_frac": round(1 - non_null / n_rows, 4) if n_rows else 0,
               "approx_distinct": distinct}
        if any(dtype.upper().startswith(t) for t in numeric_types):
            stats = con.execute(
                f"SELECT min({q}), max({q}), avg({q}), "
                f"approx_quantile({q}, 0.25), approx_quantile({q}, 0.5), "
                f"approx_quantile({q}, 0.75) FROM {src}"
            ).fetchone()
            col.update(dict(zip(
                ("min", "max", "mean", "q25", "median", "q75"),
                [round(v, 4) if isinstance(v, float) else v for v in stats])))
        elif dtype.upper().startswith(("VARCHAR", "DATE", "TIME")):
            top = con.execute(
                f"SELECT {q}, count(*) c FROM {src} WHERE {q} IS NOT NULL "
                f"GROUP BY {q} ORDER BY c DESC LIMIT 5"
            ).fetchall()
            col["top_values"] = [[str(v)[:60], c] for v, c in top]
        report["columns"].append(col)

    # markdown to stdout
    mb = report["size_bytes"] / 1e6
    print(f"# Profile: {path.name}\n")
    print(f"{n_rows:,} rows x {len(cols)} columns, {mb:,.1f} MB on disk\n")
    print("| column | type | null% | ~distinct | detail |")
    print("|---|---|---|---|---|")
    for c in report["columns"]:
        if "median" in c:
            d = (f"min {c['min']} / q25 {c['q25']} / med {c['median']} / "
                 f"q75 {c['q75']} / max {c['max']}")
        elif "top_values" in c:
            d = "; ".join(f"{v} ({n:,})" for v, n in c["top_values"][:3])
        else:
            d = ""
        print(f"| {c['name']} | {c['dtype']} | {c['null_frac']*100:.1f} "
              f"| {c['approx_distinct']:,} | {d} |")

    # quality flags
    flags = []
    for c in report["columns"]:
        if c["null_frac"] > 0.5:
            flags.append(f"{c['name']}: {c['null_frac']*100:.0f}% null")
        if c["approx_distinct"] <= 1 and n_rows > 1:
            flags.append(f"{c['name']}: constant")
        if c["approx_distinct"] >= 0.95 * n_rows and "top_values" in c:
            flags.append(f"{c['name']}: near-unique string (id-like)")
    if flags:
        print("\n**Flags:** " + "; ".join(flags))

    if json_out:
        json_out.write_text(json.dumps(report, indent=1, default=str))
        print(f"\nJSON: {json_out}")


if __name__ == "__main__":
    main()
