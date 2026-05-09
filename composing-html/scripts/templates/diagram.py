"""Diagram & illustration templates.

  - diagram.svg_figure_sheet: Page of standalone SVG figures with captions.
  - diagram.flowchart: Vertical or horizontal step flowchart with labels.
"""

from __future__ import annotations

import sys

from . import register
import composer as c


# --------------------------------------------------------------------------- #
# svg_figure_sheet                                                            #
# --------------------------------------------------------------------------- #

@register(
    "diagram.svg_figure_sheet",
    summary="Multiple SVG figures laid out as a page of captioned diagrams.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "intro_html": "Optional intro HTML.",
        "figures": "List[{label, svg: <svg>...</svg>, caption?, span?: 1|2}]. "
                   "span=2 makes a figure full width on a 2-column grid.",
    },
)
def svg_figure_sheet(spec: dict) -> dict:
    cells = []
    for f in spec.get("figures", []):
        span = int(f.get("span", 1))
        cell = (
            f'<figure class="fig" style="grid-column: span {min(span,2)};">'
            f'<div class="fig-frame">{f.get("svg","")}</div>'
            f'<figcaption>'
            f'<span class="fig-label">{c.esc(f.get("label",""))}</span>'
            + (f' <span>{c.esc(f.get("caption",""))}</span>' if f.get("caption") else "")
            + '</figcaption></figure>'
        )
        cells.append(cell)
    body = ((f'<section>{spec.get("intro_html")}</section>' if spec.get("intro_html") else "")
            + c.section(body=f'<div class="fig-grid">{"".join(cells)}</div>'))
    extra_css = """
    .fig-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 28px; }
    @media (max-width: 720px) { .fig-grid { grid-template-columns: 1fr; } .fig { grid-column: span 1 !important; } }
    .fig { margin: 0; }
    .fig-frame { background: var(--paper); border: var(--border); border-radius: var(--radius);
                 padding: 24px; display: flex; align-items: center; justify-content: center; }
    .fig-frame svg { max-width: 100%; height: auto; }
    figcaption { margin-top: 10px; font-size: 13px; color: var(--g700); }
    .fig-label { font-family: var(--mono); font-size: 11px; color: var(--clay-d); margin-right: 6px; text-transform: uppercase; letter-spacing: .06em; }
    """
    return {
        "title": spec.get("title", "Figures"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "DIAGRAMS"),
        "body": body,
        "extra_css": extra_css,
    }


# --------------------------------------------------------------------------- #
# flowchart                                                                   #
# --------------------------------------------------------------------------- #

@register(
    "diagram.flowchart",
    summary="Step-by-step flowchart (vertical or horizontal). Each step has details.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "intro_html": "Optional intro HTML.",
        "orientation": "'vertical' (default) or 'horizontal'.",
        "steps": "List[{id, label, kind?: 'start|process|decision|end', "
                 "details_html?, branches?: [{label, to_id}]}].",
    },
)
def flowchart(spec: dict) -> dict:
    orientation = spec.get("orientation", "vertical")
    steps = spec.get("steps") or []
    n = len(steps)
    # SVG layout: vertical = single column, horizontal = single row
    box_w, box_h, gap = 220, 70, 80
    if orientation == "horizontal":
        width = n * (box_w + gap)
        height = box_h + 60
    else:
        width = box_w + 60
        height = n * (box_h + gap)
    fill = {"start": "#E8EFE0", "process": "var(--paper)", "decision": "#F4D9C8", "end": "#F4DAD5"}
    stroke = {"start": "var(--ok)", "process": "var(--g300)", "decision": "var(--clay)", "end": "var(--err)"}
    pos = {}
    nodes = []
    for i, s in enumerate(steps):
        if orientation == "horizontal":
            x, y = i * (box_w + gap) + 30, 30
        else:
            x, y = 30, i * (box_h + gap) + 30
        pos[s.get("id", f"s{i}")] = (x + box_w / 2, y + box_h / 2)
        kind = s.get("kind", "process")
        if kind == "decision":
            cx, cy = x + box_w / 2, y + box_h / 2
            nodes.append(
                f'<polygon points="{cx},{y} {x+box_w},{cy} {cx},{y+box_h} {x},{cy}" '
                f'fill="{fill["decision"]}" stroke="{stroke["decision"]}" stroke-width="1.5"/>'
                f'<text x="{cx}" y="{cy+5}" text-anchor="middle" font-family="ui-sans-serif" font-size="13" font-weight="600" fill="#141413">{c.esc(s.get("label"))}</text>'
            )
        else:
            nodes.append(
                f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="8" '
                f'fill="{fill.get(kind,"var(--paper)")}" stroke="{stroke.get(kind,"var(--g300)")}" stroke-width="1.5"/>'
                f'<text x="{x+box_w/2}" y="{y+box_h/2+5}" text-anchor="middle" font-family="ui-sans-serif" font-size="13" font-weight="600" fill="#141413">{c.esc(s.get("label"))}</text>'
            )
    # Edges: sequential, plus branches
    edges = []
    for i, s in enumerate(steps):
        cur = pos[s.get("id", f"s{i}")]
        if i < n - 1 and not s.get("branches"):
            nxt = pos[steps[i + 1].get("id", f"s{i+1}")]
            edges.append(f'<line x1="{cur[0]}" y1="{cur[1]}" x2="{nxt[0]}" y2="{nxt[1]}" stroke="#9A9890" stroke-width="1.4" marker-end="url(#a)"/>')
        for br in (s.get("branches") or []):
            to_id = br.get("to_id")
            tgt = pos.get(to_id)
            if not tgt:
                print(f"composing-html warning: flowchart branch references unknown step id {to_id!r}",
                      file=sys.stderr)
                continue
            edges.append(f'<line x1="{cur[0]}" y1="{cur[1]}" x2="{tgt[0]}" y2="{tgt[1]}" stroke="#9A9890" stroke-width="1.4" marker-end="url(#a)"/>')
            mx, my = (cur[0] + tgt[0]) / 2, (cur[1] + tgt[1]) / 2
            edges.append(f'<text x="{mx}" y="{my}" font-family="ui-monospace" font-size="11" fill="#3D3D3A" text-anchor="middle" paint-order="stroke" stroke="#FAF9F5" stroke-width="3">{c.esc(br.get("label",""))}</text>')

    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px;">'
        '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 Z" fill="#9A9890"/></marker></defs>'
        + "".join(edges) + "".join(nodes) + '</svg>'
    )
    # Optional details below
    details_html = ""
    if any(s.get("details_html") for s in steps):
        rows = "".join(
            f'<details><summary>{c.esc(s.get("label"))}</summary>{s.get("details_html","")}</details>'
            for s in steps if s.get("details_html")
        )
        details_html = c.section("Step details", body=rows)
    body = ((f'<section>{spec.get("intro_html")}</section>' if spec.get("intro_html") else "")
            + c.section(body=c.card(svg)) + details_html)
    return {
        "title": spec.get("title", "Flowchart"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "FLOW"),
        "body": body,
        "page_class": "page page--wide",
    }
