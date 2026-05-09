"""Code review & understanding templates.

  - review.pr_review: PR header + per-file findings with severity tags.
  - review.code_walkthrough: Annotated explanation of a module or function.
  - review.module_map: Box-and-arrow diagram of package structure.
"""

from __future__ import annotations

from . import register
import composer as c


# --------------------------------------------------------------------------- #
# pr_review                                                                   #
# --------------------------------------------------------------------------- #

@register(
    "review.pr_review",
    summary="PR review writeup: header, summary, per-file findings with severity.",
    spec_keys={
        "title": "Page title (e.g. 'PR #247 — Review').",
        "subtitle": "Optional sub-headline.",
        "pr": "Dict {repo, number, branch, author, additions, deletions}.",
        "verdict": "Optional one-liner verdict ('approve', 'request changes', etc).",
        "summary_html": "Optional rich HTML overview (1–2 paragraphs).",
        "findings": "List[{file, line?, severity: 'info|nit|warn|block', title, body_html, snippet?, snippet_lang?}].",
    },
)
def pr_review(spec: dict) -> dict:
    pr = spec.get("pr") or {}
    pr_meta = "".join([
        c.badge(f"+{pr['additions']}", "ok") if pr.get("additions") is not None else "",
        c.badge(f"−{pr['deletions']}", "err") if pr.get("deletions") is not None else "",
        c.badge(pr.get("branch"), "info") if pr.get("branch") else "",
        c.badge(pr.get("author")) if pr.get("author") else "",
    ])
    pr_head = (
        f'<div style="font-family:var(--mono);font-size:12px;color:var(--g500);margin-bottom:8px;">'
        f'{c.esc(pr.get("repo"))}{(" · #"+str(pr.get("number"))) if pr.get("number") else ""}</div>'
        + (f'<div class="row" style="margin-top:10px;">{pr_meta}</div>' if pr_meta else "")
    )
    verdict = spec.get("verdict")
    verdict_html = c.callout(verdict, kind="info") if verdict else ""

    summary_html = spec.get("summary_html") or ""

    sev = {
        "info":  ("info",  "i"),
        "nit":   ("info",  "·"),
        "warn":  ("warn",  "!"),
        "block": ("err",   "✕"),
    }
    finding_cards = []
    for f in spec.get("findings", []):
        kind, mark = sev.get(f.get("severity", "info"), ("info", "i"))
        snippet = ""
        if f.get("snippet"):
            snippet = c.code_block(f["snippet"], lang=f.get("snippet_lang"))
        loc = f.get("file", "")
        if f.get("line") is not None:
            loc = f"{loc}:{f['line']}"
        body = (
            f'<div class="row" style="justify-content:space-between;align-items:flex-start;">'
            f'<div><div style="font-family:var(--mono);font-size:12px;color:var(--g500);">{c.esc(loc)}</div>'
            f'<h3 style="margin-top:4px;">{c.esc(f.get("title"))}</h3></div>'
            f'{c.badge(f.get("severity","info").upper(), kind)}</div>'
            + f'<div style="margin-top:10px;">{f.get("body_html","")}</div>'
            + (f'<div style="margin-top:10px;">{snippet}</div>' if snippet else "")
        )
        finding_cards.append(c.card(body))

    body = (
        c.section(body=c.card(pr_head + (f'<div style="margin-top:14px;">{verdict_html}</div>' if verdict_html else "")))
        + (c.section("Summary", body=summary_html) if summary_html else "")
        + c.section("Findings", body=c.stack(finding_cards) if finding_cards else "<p>No findings.</p>")
    )
    return {
        "title": spec.get("title", "Review"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "CODE REVIEW"),
        "body": body,
    }


# --------------------------------------------------------------------------- #
# code_walkthrough                                                            #
# --------------------------------------------------------------------------- #

@register(
    "review.code_walkthrough",
    summary="Annotated walkthrough of code: numbered steps with snippets and prose.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "intro_html": "Optional introduction HTML.",
        "steps": "List[{heading, body_html, code?, lang?}].",
    },
)
def code_walkthrough(spec: dict) -> dict:
    rows = []
    for i, s in enumerate(spec.get("steps", []), start=1):
        snippet = c.code_block(s["code"], lang=s.get("lang")) if s.get("code") else ""
        rows.append(
            f'<div style="display:grid;grid-template-columns:48px 1fr;gap:18px;margin-bottom:32px;">'
            f'<div style="font-family:var(--serif);font-size:32px;color:var(--clay);line-height:1;">{i:02d}</div>'
            f'<div><h3>{c.esc(s.get("heading"))}</h3>'
            f'<div style="margin:8px 0 12px;">{s.get("body_html","")}</div>'
            f'{snippet}</div></div>'
        )
    body = ((f'<section>{spec.get("intro_html")}</section>' if spec.get("intro_html") else "")
            + c.section(body="".join(rows)))
    return {
        "title": spec.get("title", "Walkthrough"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "WALKTHROUGH"),
        "body": body,
        "page_class": "page page--narrow",
    }


# --------------------------------------------------------------------------- #
# module_map                                                                  #
# --------------------------------------------------------------------------- #

@register(
    "review.module_map",
    summary="Module map: nodes (modules) and edges (dependencies) as SVG boxes/arrows.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "intro_html": "Optional intro HTML.",
        "nodes": "List[{id, label, description?, x?: int, y?: int, kind?: 'core|util|external'}]. "
                 "If x/y are missing, nodes are auto-laid in a grid.",
        "edges": "List[{from: id, to: id, label?}].",
        "legend": "Optional list[{label, kind}] to render a legend.",
    },
)
def module_map(spec: dict) -> dict:
    nodes = spec.get("nodes") or []
    edges = spec.get("edges") or []
    # Auto-layout: 3 cols if any node lacks coordinates
    if any(n.get("x") is None or n.get("y") is None for n in nodes):
        cols = 3
        cw, ch = 220, 110
        for i, n in enumerate(nodes):
            n["x"] = (i % cols) * cw + 30
            n["y"] = (i // cols) * ch + 30
    nw, nh = 180, 70
    width  = max((n["x"] + nw + 30) for n in nodes) if nodes else 600
    height = max((n["y"] + nh + 30) for n in nodes) if nodes else 400
    color = {"core": "#FCEEDE", "util": "#EAE8DF", "external": "#E0E7DA"}
    border = {"core": "var(--clay)", "util": "var(--g300)", "external": "var(--olive)"}
    by_id = {n["id"]: n for n in nodes}

    edge_svg = []
    for e in edges:
        a, b = by_id.get(e.get("from")), by_id.get(e.get("to"))
        if not a or not b: continue
        x1, y1 = a["x"] + nw / 2, a["y"] + nh / 2
        x2, y2 = b["x"] + nw / 2, b["y"] + nh / 2
        edge_svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#9A9890" stroke-width="1.4" marker-end="url(#arrow)"/>'
        )
        if e.get("label"):
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            edge_svg.append(
                f'<text x="{mx}" y="{my}" font-family="ui-monospace" font-size="10" fill="#87867F" '
                f'text-anchor="middle" paint-order="stroke" stroke="#FAF9F5" stroke-width="3">{c.esc(e["label"])}</text>'
            )

    node_svg = []
    for n in nodes:
        kind = n.get("kind", "util")
        node_svg.append(
            f'<g transform="translate({n["x"]},{n["y"]})">'
            f'<rect width="{nw}" height="{nh}" rx="8" fill="{color.get(kind, "#EAE8DF")}" '
            f'stroke="{border.get(kind, "var(--g300)")}" stroke-width="1.5"/>'
            f'<text x="14" y="26" font-family="ui-sans-serif" font-size="14" font-weight="600" fill="#141413">{c.esc(n.get("label"))}</text>'
            + (f'<text x="14" y="46" font-family="ui-monospace" font-size="11" fill="#3D3D3A">{c.esc(n.get("description"))}</text>' if n.get("description") else "")
            + '</g>'
        )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px;">'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 Z" fill="#9A9890"/></marker></defs>'
        + "".join(edge_svg) + "".join(node_svg)
        + '</svg>'
    )
    legend_html = ""
    if spec.get("legend"):
        legend_html = '<div class="row" style="margin-top:18px;">' + "".join(
            f'<span class="badge" style="background:{color.get(item.get("kind","util"))};">{c.esc(item.get("label"))}</span>'
            for item in spec["legend"]) + '</div>'
    body = ((f'<section>{spec.get("intro_html")}</section>' if spec.get("intro_html") else "")
            + c.section(body=c.card(svg + legend_html, soft=False)))
    return {
        "title": spec.get("title", "Module map"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "ARCHITECTURE"),
        "body": body,
        "page_class": "page page--wide",
    }
