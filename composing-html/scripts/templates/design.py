"""Design templates.

  - design.design_system: Color swatches, typography scale, spacing tokens.
  - design.component_variants: Grid of component states/sizes/intents.
"""

from __future__ import annotations

from . import register
import composer as c


# --------------------------------------------------------------------------- #
# design_system                                                               #
# --------------------------------------------------------------------------- #

@register(
    "design.design_system",
    summary="Design system reference: color swatches, type scale, spacing tokens.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "colors": "Dict[group_name -> List[{name, hex, token?}]] — e.g. {'Brand': [{'name':'Clay','hex':'#D97757','token':'--clay'}]}.",
        "typography": "List[{name, font_family, size, weight?, line_height?, sample?}].",
        "spacing": "List[{name, px}] — rendered as a horizontal ruler.",
        "radii": "Optional list[{name, px}].",
    },
)
def design_system(spec: dict) -> dict:
    sections = []

    colors = spec.get("colors") or {}
    if colors:
        groups = []
        for group, items in colors.items():
            chips = []
            for item in items:
                hex_v = item.get("hex", "#000")
                chips.append(
                    f'<div><div style="width:64px;height:64px;border-radius:8px;background:{c.esc(hex_v)};'
                    f'border:1px solid var(--g200);margin-bottom:6px;"></div>'
                    f'<div style="font-family:var(--mono);font-size:11px;color:var(--g700);">{c.esc(item.get("name"))}</div>'
                    f'<div style="font-family:var(--mono);font-size:11px;color:var(--g500);">{c.esc(hex_v)}</div>'
                    + (f'<div style="font-family:var(--mono);font-size:11px;color:var(--g500);">{c.esc(item.get("token"))}</div>' if item.get("token") else "")
                    + '</div>'
                )
            groups.append(
                f'<div style="margin-bottom:28px;">'
                f'<div style="font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--g500);margin-bottom:12px;">{c.esc(group)}</div>'
                f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:18px;">{"".join(chips)}</div>'
                f'</div>'
            )
        sections.append(c.section("Color", body="".join(groups)))

    typography = spec.get("typography") or []
    if typography:
        rows = []
        for t in typography:
            style = (f'font-family:{c.esc(t.get("font_family","var(--sans)"))};'
                     f'font-size:{c.esc(t.get("size","16px"))};'
                     f'line-height:{c.esc(t.get("line_height","1.4"))};'
                     f'font-weight:{c.esc(t.get("weight","400"))};')
            sample = c.esc(t.get("sample", "The quick brown fox jumps over the lazy dog."))
            rows.append(
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:24px;'
                f'padding:18px 22px;border-bottom:1px solid var(--g150);">'
                f'<div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;{style}">{sample}</div>'
                f'<div style="font-family:var(--mono);font-size:12px;color:var(--g500);text-align:right;flex-shrink:0;">'
                f'<div style="color:var(--g700);">{c.esc(t.get("name"))}</div>'
                f'<div>{c.esc(t.get("size",""))} / {c.esc(t.get("weight",""))}</div></div></div>'
            )
        sections.append(c.section("Typography",
            body=f'<div class="card" style="padding:0;overflow:hidden;">{"".join(rows)}</div>'))

    spacing = spec.get("spacing") or []
    if spacing:
        bars = []
        for s in spacing:
            px = int(s.get("px", 0))
            bars.append(
                f'<div style="display:flex;flex-direction:column;align-items:center;gap:8px;">'
                f'<div style="background:var(--clay);border-radius:3px;height:14px;width:{max(px,4)}px;"></div>'
                f'<div style="font-family:var(--mono);font-size:11px;color:var(--g700);text-align:center;">{c.esc(s.get("name"))}'
                f'<div style="color:var(--g500);">{px}px</div></div></div>'
            )
        sections.append(c.section("Spacing",
            body=f'<div class="card" style="display:flex;align-items:flex-end;gap:28px;overflow-x:auto;">{"".join(bars)}</div>'))

    radii = spec.get("radii") or []
    if radii:
        chips = []
        for r in radii:
            px = int(r.get("px", 0))
            chips.append(
                f'<div style="display:flex;flex-direction:column;align-items:center;gap:8px;">'
                f'<div style="width:64px;height:64px;background:var(--oat);border:1.5px solid var(--clay);border-radius:{px}px;"></div>'
                f'<div style="font-family:var(--mono);font-size:11px;color:var(--g700);text-align:center;">{c.esc(r.get("name"))}'
                f'<div style="color:var(--g500);">{px}px</div></div></div>'
            )
        sections.append(c.section("Radius",
            body=f'<div class="card" style="display:flex;gap:28px;flex-wrap:wrap;">{"".join(chips)}</div>'))

    return {
        "title": spec.get("title", "Design system"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "DESIGN SYSTEM"),
        "body": "".join(sections),
    }


# --------------------------------------------------------------------------- #
# component_variants                                                          #
# --------------------------------------------------------------------------- #

@register(
    "design.component_variants",
    summary="Component variants grid: every size/state/intent of a UI component.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "components": "List[{name, description?, axes: {axis_name: [labels...]}, "
                      "cells: [{coords: {axis_name: label,...}, html}]}]. "
                      "Cells are rendered as a grid; axes drive row/column headers.",
    },
)
def component_variants(spec: dict) -> dict:
    sections = []
    for comp in spec.get("components", []):
        axes = comp.get("axes") or {}
        cells = comp.get("cells") or []
        axis_names = list(axes.keys())

        if len(axis_names) >= 2:
            rows_axis, cols_axis = axis_names[0], axis_names[1]
            row_labels, col_labels = axes[rows_axis], axes[cols_axis]
            lookup: dict[tuple, str] = {}
            for cell in cells:
                co = cell.get("coords") or {}
                lookup[(co.get(rows_axis), co.get(cols_axis))] = cell.get("html", "")
            head = "<tr><th></th>" + "".join(f"<th>{c.esc(cl)}</th>" for cl in col_labels) + "</tr>"
            body_rows = []
            for rl in row_labels:
                tds = "".join(
                    f'<td style="background:var(--paper);padding:14px;">{lookup.get((rl, cl), "")}</td>'
                    for cl in col_labels
                )
                body_rows.append(f'<tr><th style="text-align:left;">{c.esc(rl)}</th>{tds}</tr>')
            grid_html = f'<table>{head}{"".join(body_rows)}</table>'
        else:
            grid_html = c.grid([
                c.card(
                    cell.get("html", ""),
                    title=", ".join(f"{k}: {v}" for k, v in (cell.get("coords") or {}).items()) or None,
                )
                for cell in cells
            ], cols="auto")

        sections.append(c.section(
            comp.get("name"),
            body=(f'<p style="color:var(--g700);margin-bottom:18px;">{c.esc(comp.get("description"))}</p>'
                  if comp.get("description") else "") + grid_html,
        ))
    return {
        "title": spec.get("title", "Component variants"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "COMPONENTS"),
        "body": "".join(sections),
        "page_class": "page page--wide",
    }
