#!/usr/bin/env python3
"""Turn an EDA profile into a clean, self-contained visual dashboard.

The ydata HTML report is exhaustive but visually noisy; the DuckDB large-file
path emits only text/JSON. This script reads either JSON shape and renders a
single standalone HTML file with a handful of Chart.js charts that carry the
findings worth seeing: missingness by column, the most skewed / zero-inflated
distributions, and the largest categorical breakdowns.

Usage:
  python3 visualize_findings.py <report.json> [--out findings.html] [--top N]

Accepts:
  - ydata-profiling JSON (has top-level "variables" + "table")
  - profile_large.py --json output (has top-level "columns")

Output: one HTML file, no external data, Chart.js from cdnjs. Open directly or
hand to the user. Charts are flat, dark-mode aware, and each has an aria-label.
"""
import argparse
import html
import json
import sys
from pathlib import Path

CDN = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"
# Cove categorical order (light-mode hexes); charts pick from these by slot.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
GOOD, BAD, NEUTRAL = "#1baf7a", "#e34948", "#378add"


def _pct(x):
    try:
        return round(float(x) * 100, 1)
    except (TypeError, ValueError):
        return None


def load(path):
    d = json.loads(Path(path).read_text())
    if "variables" in d and "table" in d:
        return _from_ydata(d)
    if "columns" in d:
        return _from_large(d)
    sys.exit("Unrecognized JSON: expected ydata ('variables') or profile_large ('columns') shape.")


def _from_ydata(d):
    t = d["table"]
    n = t.get("n")
    vars_ = d["variables"]
    cols = []
    for name, v in vars_.items():
        typ = v.get("type")
        rec = {
            "name": name,
            "type": typ,
            "p_missing": _pct(v.get("p_missing")),
            "n_distinct": v.get("n_distinct"),
        }
        if typ == "Numeric":
            rec["skewness"] = v.get("skewness")
            rec["p_zeros"] = _pct(v.get("p_zeros"))
            h = v.get("histogram") or {}
            counts = h.get("counts")
            edges = h.get("bin_edges")
            if counts and edges and len(edges) == len(counts) + 1:
                rec["hist"] = {
                    "counts": counts,
                    "labels": [f"{edges[i]:.2g}" for i in range(len(counts))],
                }
        elif typ in ("Categorical", "Text", "Boolean"):
            vc = v.get("value_counts_without_nan") or {}
            rec["value_counts"] = list(vc.items())[:12]
        cols.append(rec)
    return {
        "title": d.get("analysis", {}).get("title", "Dataset"),
        "n_rows": n,
        "n_cols": t.get("n_var"),
        "p_cells_missing": _pct(t.get("p_cells_missing")),
        "alerts": d.get("alerts", []),
        "columns": cols,
    }


def _from_large(d):
    cols = []
    for c in d["columns"]:
        rec = {
            "name": c.get("name"),
            "type": c.get("type", ""),
            "p_missing": _pct(c.get("null_frac")) if c.get("null_frac") is not None
            else c.get("null_pct"),
            "n_distinct": c.get("approx_distinct") or c.get("n_distinct"),
        }
        top = c.get("top_values") or c.get("top")
        if top:
            rec["value_counts"] = [(str(k), val) for k, val in
                                   (top.items() if isinstance(top, dict) else top)][:12]
        cols.append(rec)
    return {
        "title": d.get("file", "Dataset"),
        "n_rows": d.get("n_rows"),
        "n_cols": len(cols),
        "p_cells_missing": None,
        "alerts": d.get("flags", []),
        "columns": cols,
    }


def build_charts(data, top):
    """Return list of chart dicts: {id, kind, aria, cfg, note}."""
    charts = []
    cols = data["columns"]

    # 1) Missingness by column (only columns that have any). Sorted desc, capped.
    miss = [(c["name"], c["p_missing"]) for c in cols
            if c.get("p_missing")]
    miss.sort(key=lambda x: -x[1])
    if miss:
        miss = miss[:max(top, 12)]
        charts.append({
            "id": "miss",
            "aria": "Missing data percentage by column.",
            "note": "Columns with any missing values, worst first. Red ≥ 50%.",
            "cfg": {
                "type": "bar",
                "data": {"labels": [m[0] for m in miss],
                         "datasets": [{"data": [m[1] for m in miss],
                                       "backgroundColor": [BAD if m[1] >= 50 else GOOD for m in miss],
                                       "borderRadius": 4, "borderSkipped": False}]},
                "options": _hbar_opts("% missing", 0, 100, pct=True,
                                      height=max(200, 26 * len(miss) + 60)),
            },
        })

    # 2) Most skewed / zero-inflated numeric distributions — small-multiple histograms.
    nums = [c for c in cols if c.get("hist")]
    def _severity(c):
        return max(abs(c.get("skewness") or 0), (c.get("p_zeros") or 0) / 10)
    nums.sort(key=_severity, reverse=True)
    for i, c in enumerate(nums[:min(top, 6)]):
        tags = []
        if c.get("skewness") is not None and abs(c["skewness"]) >= 2:
            tags.append(f"skew {c['skewness']:.1f}")
        if c.get("p_zeros") and c["p_zeros"] >= 40:
            tags.append(f"{c['p_zeros']:.0f}% zeros")
        charts.append({
            "id": f"hist{i}",
            "aria": f"Distribution histogram of {c['name']}.",
            "note": f"{c['name']}" + (f" — {', '.join(tags)}" if tags else ""),
            "half": True,
            "cfg": {
                "type": "bar",
                "data": {"labels": c["hist"]["labels"],
                         "datasets": [{"data": c["hist"]["counts"],
                                       "backgroundColor": NEUTRAL,
                                       "borderRadius": 2, "borderSkipped": False,
                                       "barPercentage": 1.0, "categoryPercentage": 1.0}]},
                "options": _vbar_opts(height=220),
            },
        })

    # 3) Largest categorical breakdowns (excluding near-unique id-like columns).
    cats = [c for c in cols if c.get("value_counts")
            and c.get("n_distinct") and 1 < c["n_distinct"] <= 15]
    cats.sort(key=lambda c: c["n_distinct"])
    for i, c in enumerate(cats[:min(top, 4)]):
        vc = c["value_counts"]
        charts.append({
            "id": f"cat{i}",
            "aria": f"Value counts for {c['name']}.",
            "note": f"{c['name']} — {c['n_distinct']} distinct",
            "half": True,
            "cfg": {
                "type": "bar",
                "data": {"labels": [str(k) for k, _ in vc],
                         "datasets": [{"data": [val for _, val in vc],
                                       "backgroundColor": [SERIES[j % len(SERIES)] for j in range(len(vc))],
                                       "borderRadius": 4, "borderSkipped": False}]},
                "options": _hbar_opts("count", height=max(160, 24 * len(vc) + 50)),
            },
        })
    return charts


def _hbar_opts(x_title, xmin=None, xmax=None, pct=False, height=300):
    x = {"title": {"display": True, "text": x_title, "color": "#898781",
                   "font": {"size": 11}},
         "ticks": {"color": "#898781"}, "grid": {"color": "#e1e0d9"}}
    if xmin is not None:
        x["min"] = xmin
    if xmax is not None:
        x["max"] = xmax
    if pct:
        x["ticks"]["callback"] = "__PCT__"
    return {"indexAxis": "y", "responsive": True, "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {"x": x,
                       "y": {"ticks": {"color": "#52514e", "font": {"size": 12}},
                             "grid": {"display": False}}},
            "__height__": height}


def _vbar_opts(height=220):
    return {"responsive": True, "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {"x": {"ticks": {"color": "#898781", "maxTicksLimit": 6,
                                       "maxRotation": 0, "font": {"size": 10}},
                             "grid": {"display": False}},
                       "y": {"ticks": {"color": "#898781"}, "grid": {"color": "#e1e0d9"},
                             "type": "logarithmic"}},
            "__height__": height}


def render(data, charts):
    def js(cfg):
        h = cfg["options"].pop("__height__", 300)
        s = json.dumps(cfg)
        s = s.replace('"__PCT__"', "(v)=>v+'%'")
        return s, h

    cards = []
    specs = []
    for c in charts:
        cfg_json, h = js(c["cfg"])
        cls = "card half" if c.get("half") else "card"
        cards.append(f"""<div class="{cls}">
<div class="note">{html.escape(c['note'])}</div>
<div class="wrap" style="height:{h}px"><canvas id="{c['id']}" role="img" aria-label="{html.escape(c['aria'])}"></canvas></div>
</div>""")
        specs.append(f'["{c["id"]}",{cfg_json}]')
    init = ("<script>function __draw(){if(typeof Chart===\"undefined\"){"
            "document.querySelectorAll('.wrap').forEach(w=>w.innerHTML="
            "'<div style=\\'color:var(--mut);font-size:13px;padding:20px 0\\'>chart library did not load</div>');return;}"
            "[" + ",".join(specs) + "].forEach(([id,cfg])=>"
            "new Chart(document.getElementById(id),cfg));}"
            "if(window.Chart)__draw();else window.addEventListener('load',__draw);</script>")

    alerts = "".join(f"<li>{html.escape(str(a))}</li>" for a in data["alerts"][:12])
    miss_line = (f' · {data["p_cells_missing"]}% cells missing'
                 if data.get("p_cells_missing") else "")
    rows = f'{data["n_rows"]:,}' if data.get("n_rows") else "?"

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Findings — {html.escape(str(data['title']))}</title>
<script src="{CDN}"></script>
<style>
:root{{--fg:#0b0b0b;--fg2:#52514e;--mut:#898781;--bg:#fcfcfb;--card:#fff;--bd:#e1e0d9}}
@media(prefers-color-scheme:dark){{:root{{--fg:#fff;--fg2:#c3c2b7;--mut:#898781;--bg:#161615;--card:#1e1e1c;--bd:#2c2c2a}}}}
*{{box-sizing:border-box}}
body{{margin:0;padding:28px;background:var(--bg);color:var(--fg);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.5}}
.head{{max-width:1080px;margin:0 auto 20px}}
h1{{font-size:22px;font-weight:500;margin:0 0 4px}}
.sub{{color:var(--mut);font-size:13px}}
.grid{{max-width:1080px;margin:0 auto;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}
.card{{grid-column:span 2;background:var(--card);border:.5px solid var(--bd);border-radius:12px;padding:14px 16px}}
.card.half{{grid-column:span 1}}
.note{{font-size:13px;color:var(--fg2);margin-bottom:8px}}
.wrap{{position:relative;width:100%}}
.alerts{{max-width:1080px;margin:20px auto 0;font-size:13px;color:var(--fg2)}}
.alerts h2{{font-size:14px;font-weight:500;color:var(--fg)}}
.alerts ul{{margin:6px 0 0;padding-left:18px}}
@media(max-width:640px){{.card.half{{grid-column:span 2}}}}
</style></head><body>
<div class="head"><h1>{html.escape(str(data['title']))}</h1>
<div class="sub">{rows} rows · {data.get('n_cols','?')} columns{miss_line}</div></div>
<div class="grid">
{''.join(cards)}
</div>
{f'<div class="alerts"><h2>Quality alerts</h2><ul>{alerts}</ul></div>' if alerts else ''}
{init}
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", help="eda_report.json or profile_large --json output")
    ap.add_argument("--out", default="/mnt/user-data/outputs/eda_findings.html")
    ap.add_argument("--top", type=int, default=6,
                    help="max charts per category (default 6)")
    a = ap.parse_args()
    data = load(a.report)
    charts = build_charts(data, a.top)
    if not charts:
        sys.exit("No chartable findings in report.")
    Path(a.out).write_text(render(data, charts))
    print(f"\u2713 Findings dashboard: {a.out}")
    print(f"  {len(charts)} charts from {data.get('n_cols','?')} columns, "
          f"{data.get('n_rows','?'):,} rows" if data.get('n_rows')
          else f"  {len(charts)} charts")


if __name__ == "__main__":
    main()
