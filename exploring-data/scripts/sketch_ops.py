#!/usr/bin/env python3
"""Sketch-based exploration ops that profilers miss. Fixed memory, any file size.

Subcommands:
  dups <file> [--threshold 0.9] [--cols a,b]   near-duplicate row detection (MinHash LSH)
  overlap <fileA> <fileB> --key <col> [--key-b <col>]   key overlap / join feasibility (theta sketch)
  snapshot <file> --out <sketches.json>        persist HLL+KLL sketches per column
  drift <file> --baseline <sketches.json>      compare current file against a snapshot

Files stream through DuckDB in batches; sketches are the only state held.
"""
import base64
import json
import sys
from pathlib import Path

try:
    import duckdb
    from datasketches import (hll_sketch, kll_floats_sketch,
                              update_theta_sketch, theta_intersection,
                              theta_union)
    from datasketch import MinHash, MinHashLSH
except ImportError as e:
    sys.exit(f"Missing dep ({e.name}) — run install_large.sh first")

BATCH = 50_000


def reader_sql(path: Path) -> str:
    s = path.suffix.lower()
    p = str(path).replace("'", "''")
    return {
        ".csv": f"read_csv_auto('{p}', sample_size=-1)",
        ".tsv": f"read_csv_auto('{p}', sample_size=-1)",
        ".parquet": f"read_parquet('{p}')",
        ".json": f"read_json_auto('{p}')",
        ".ndjson": f"read_json_auto('{p}')",
        ".jsonl": f"read_json_auto('{p}')",
    }.get(s) or sys.exit(f"Unsupported format: {s}")


def batches(con, sql):
    cur = con.execute(sql)
    while rows := cur.fetchmany(BATCH):
        yield rows


def cmd_dups(argv):
    path = Path(argv[0])
    thresh = float(argv[argv.index("--threshold") + 1]) if "--threshold" in argv else 0.9
    con = duckdb.connect()
    src = reader_sql(path)
    cols = ('"' + '", "'.join(argv[argv.index("--cols") + 1].split(",")) + '"'
            ) if "--cols" in argv else "*"
    lsh = MinHashLSH(threshold=thresh, num_perm=128)
    exact_seen, exact_dups, clusters, i = set(), 0, [], 0
    for rows in batches(con, f"SELECT {cols} FROM {src}"):
        for row in rows:
            i += 1
            key = tuple(str(v) for v in row)
            if key in exact_seen:
                exact_dups += 1
                continue
            exact_seen.add(key)
            m = MinHash(num_perm=128)
            for tok in " ".join(key).lower().split():
                m.update(tok.encode())
            near = lsh.query(m)
            if near:
                clusters.append((near[0], i))
            lsh.insert(f"row{i}", m)
    print(f"# Near-duplicate scan: {path.name}")
    print(f"{i:,} rows; {exact_dups:,} exact duplicates; "
          f"{len(clusters):,} near-duplicate pairs at Jaccard>={thresh}")
    for anchor, dup in clusters[:10]:
        print(f"  {anchor} ~ row{dup}")
    if len(clusters) > 10:
        print(f"  ... {len(clusters) - 10} more")


def _theta_of(path, key):
    con = duckdb.connect()
    sk = update_theta_sketch()
    n = 0
    for rows in batches(con, f'SELECT "{key}" FROM {reader_sql(path)} '
                             f'WHERE "{key}" IS NOT NULL'):
        for (v,) in rows:
            sk.update(str(v))
            n += 1
    return sk, n


def cmd_overlap(argv):
    a, b = Path(argv[0]), Path(argv[1])
    key = argv[argv.index("--key") + 1]
    key_b = argv[argv.index("--key-b") + 1] if "--key-b" in argv else key
    sa, na = _theta_of(a, key)
    sb, nb = _theta_of(b, key_b)
    inter = theta_intersection()
    inter.update(sa)
    inter.update(sb)
    uni = theta_union()
    uni.update(sa)
    uni.update(sb)
    i, u = inter.get_result().get_estimate(), uni.get_result().get_estimate()
    ea, eb = sa.get_estimate(), sb.get_estimate()
    print(f"# Key overlap: {a.name}.{key} vs {b.name}.{key_b}")
    print(f"A: {na:,} values, ~{ea:,.0f} distinct")
    print(f"B: {nb:,} values, ~{eb:,.0f} distinct")
    print(f"Intersection ~{i:,.0f} | Jaccard ~{i/u:.3f}" if u else "empty")
    if ea:
        print(f"~{i/ea*100:.1f}% of A's keys appear in B; "
              f"~{i/eb*100:.1f}% of B's in A" if eb else "")


def _snapshot(path):
    con = duckdb.connect()
    src = reader_sql(path)
    cols = con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()
    numeric = ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "FLOAT", "DOUBLE",
               "DECIMAL", "HUGEINT")
    out = {"file": path.name, "rows": 0, "cols": {}}
    hll = {n: hll_sketch(12) for n, *_ in cols}
    kll = {n: kll_floats_sketch(200) for n, t, *_ in cols
           if any(t.upper().startswith(x) for x in numeric)}
    names = [n for n, *_ in cols]
    for rows in batches(con, f"SELECT * FROM {src}"):
        out["rows"] += len(rows)
        for row in rows:
            for n, v in zip(names, row):
                if v is None:
                    continue
                hll[n].update(str(v))
                if n in kll:
                    kll[n].update(float(v))
    for n in names:
        out["cols"][n] = {
            "hll": base64.b64encode(hll[n].serialize_compact()).decode()}
        if n in kll and not kll[n].is_empty():
            out["cols"][n]["kll"] = base64.b64encode(
                kll[n].serialize()).decode()
    return out


def cmd_snapshot(argv):
    path = Path(argv[0])
    out = Path(argv[argv.index("--out") + 1])
    snap = _snapshot(path)
    out.write_text(json.dumps(snap))
    print(f"Snapshot: {snap['rows']:,} rows, {len(snap['cols'])} columns "
          f"-> {out} ({out.stat().st_size/1024:.1f} KB)")


def cmd_drift(argv):
    path = Path(argv[0])
    base = json.loads(Path(argv[argv.index("--baseline") + 1]).read_text())
    cur = _snapshot(path)
    print(f"# Drift: {path.name} vs baseline {base['file']}")
    print(f"Rows: {base['rows']:,} -> {cur['rows']:,}")
    gone = set(base["cols"]) - set(cur["cols"])
    new = set(cur["cols"]) - set(base["cols"])
    if gone:
        print(f"Columns dropped: {sorted(gone)}")
    if new:
        print(f"Columns added: {sorted(new)}")
    for n in sorted(set(base["cols"]) & set(cur["cols"])):
        b, c = base["cols"][n], cur["cols"][n]
        hb = hll_sketch.deserialize(base64.b64decode(b["hll"]))
        hc = hll_sketch.deserialize(base64.b64decode(c["hll"]))
        eb, ec = hb.get_estimate(), hc.get_estimate()
        notes = []
        if eb and abs(ec - eb) / eb > 0.10:
            notes.append(f"distinct ~{eb:,.0f} -> ~{ec:,.0f}")
        if "kll" in b and "kll" in c:
            kb = kll_floats_sketch.deserialize(base64.b64decode(b["kll"]))
            kc = kll_floats_sketch.deserialize(base64.b64decode(c["kll"]))
            qb = [kb.get_quantile(q) for q in (0.25, 0.5, 0.75)]
            qc = [kc.get_quantile(q) for q in (0.25, 0.5, 0.75)]
            span = (qb[2] - qb[0]) or 1.0
            if any(abs(x - y) / abs(span) > 0.10 for x, y in zip(qb, qc)):
                notes.append(f"quantiles {[round(v,2) for v in qb]} -> "
                             f"{[round(v,2) for v in qc]}")
        if notes:
            print(f"  {n}: " + "; ".join(notes))
    print("(threshold: >10% shift in distinct count or IQR-relative quantiles)")


if __name__ == "__main__":
    cmds = {"dups": cmd_dups, "overlap": cmd_overlap,
            "snapshot": cmd_snapshot, "drift": cmd_drift}
    if len(sys.argv) < 3 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]](sys.argv[2:])
