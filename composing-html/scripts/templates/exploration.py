"""Exploration & planning templates.

  - exploration.comparison_grid : N options side-by-side with pros/cons/tags.
  - exploration.design_directions: Visual direction cards with sample swatches.
  - exploration.implementation_plan: Milestones, risks, and a flow sketch.
"""

from __future__ import annotations

from . import register
import composer as c


# --------------------------------------------------------------------------- #
# comparison_grid                                                             #
# --------------------------------------------------------------------------- #

@register(
    "exploration.comparison_grid",
    summary="N options side-by-side: verdict, summary, pros, cons, tags.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "options": "List[{name, verdict, summary, pros[], cons[], tags[]}].",
        "recommendation": "Optional name of the recommended option (highlighted).",
    },
)
def comparison_grid(spec: dict) -> dict:
    options = spec.get("options", [])
    rec = spec.get("recommendation")
    cards = []
    for opt in options:
        is_rec = rec and opt.get("name") == rec
        head_badge = c.badge("recommended", "clay") if is_rec else ""
        body = (
            (f'<div class="row" style="justify-content:space-between;align-items:flex-start;">'
             f'<h3>{c.esc(opt.get("name"))}</h3>{head_badge}</div>')
            + (f'<p style="font-style:italic;color:var(--clay-d);margin:4px 0 12px;">{c.esc(opt.get("verdict"))}</p>' if opt.get("verdict") else "")
            + (f'<p style="margin:0 0 16px;">{c.esc(opt.get("summary"))}</p>' if opt.get("summary") else "")
            + (f'<div style="font-family:var(--mono);font-size:11px;color:var(--ok);margin-bottom:4px;">PROS</div>{c.bullets(opt.get("pros") or [])}' if opt.get("pros") else "")
            + (f'<div style="font-family:var(--mono);font-size:11px;color:var(--err);margin:14px 0 4px;">CONS</div>{c.bullets(opt.get("cons") or [])}' if opt.get("cons") else "")
            + (f'<div class="row" style="margin-top:16px;">{"".join(c.badge(t) for t in (opt.get("tags") or []))}</div>' if opt.get("tags") else "")
        )
        cards.append(c.card(body, elev=is_rec, extra_class="opt-card" + (" opt-rec" if is_rec else "")))
    body_html = c.section(body=c.grid(cards, cols=min(3, max(1, len(cards)))))

    extra_css = """
    .opt-card { display: flex; flex-direction: column; }
    .opt-rec  { border-color: var(--clay); border-width: 2px; }
    """
    return {
        "title": spec.get("title", "Comparison"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "EXPLORATION"),
        "body": body_html,
        "extra_css": extra_css,
    }


# --------------------------------------------------------------------------- #
# design_directions                                                           #
# --------------------------------------------------------------------------- #

@register(
    "exploration.design_directions",
    summary="Visual design directions: name, vibe, palette swatches, sample type.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "directions": "List[{name, vibe, palette: [hex...], typography: {display, body}, notes}].",
    },
)
def design_directions(spec: dict) -> dict:
    cards = []
    for d in spec.get("directions", []):
        palette = d.get("palette") or []
        swatches = "".join(
            f'<div style="background:{c.css_color(hx, default="#ccc")};height:48px;border-radius:6px;'
            f'border:1px solid rgba(0,0,0,.06);" title="{c.esc(hx)}"></div>'
            for hx in palette
        )
        typo = d.get("typography") or {}
        sample = ""
        if typo:
            disp = c.esc(typo.get("display", "Aa"))
            body = c.esc(typo.get("body", "The quick brown fox jumps over the lazy dog."))
            sample = (f'<div style="margin-top:14px;padding:14px;background:var(--g100);border-radius:8px;">'
                      f'<div style="font-family:var(--serif);font-size:30px;line-height:1;margin-bottom:6px;">{disp}</div>'
                      f'<div style="font-size:13px;color:var(--g700);">{body}</div></div>')
        body = (
            f'<h3>{c.esc(d.get("name"))}</h3>'
            + (f'<p style="color:var(--clay-d);margin:2px 0 14px;">{c.esc(d.get("vibe"))}</p>' if d.get("vibe") else "")
            + (f'<div style="display:grid;grid-template-columns:repeat({len(palette) or 1},1fr);gap:6px;">{swatches}</div>' if palette else "")
            + sample
            + (f'<p style="margin-top:14px;font-size:14px;color:var(--g700);">{c.esc(d.get("notes"))}</p>' if d.get("notes") else "")
        )
        cards.append(c.card(body))
    body_html = c.section(body=c.grid(cards, cols=min(3, max(1, len(cards)))))
    return {
        "title": spec.get("title", "Design directions"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "EXPLORATION"),
        "body": body_html,
    }


# --------------------------------------------------------------------------- #
# implementation_plan                                                         #
# --------------------------------------------------------------------------- #

@register(
    "exploration.implementation_plan",
    summary="Implementation plan: milestones, owners, risks, and an optional flow sketch.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "summary_html": "Optional rich HTML intro (one or two paragraphs).",
        "milestones": "List[{name, when, owner?, deliverables: [str], status?: 'done|active|next|later'}].",
        "risks": "List[{risk, likelihood: 'low|med|high', impact: 'low|med|high', mitigation}].",
        "data_flow": "Optional list of strings; rendered as arrow-connected boxes (left-to-right).",
    },
)
def implementation_plan(spec: dict) -> dict:
    # Milestones as a vertical timeline
    status_color = {"done": "var(--ok)", "active": "var(--clay)", "next": "var(--info)", "later": "var(--g500)"}
    owner_style = "font-family:var(--mono);font-size:12px;color:var(--g500);margin-bottom:6px;"
    ms_rows = []
    for m in spec.get("milestones", []):
        sc = status_color.get(m.get("status", "next"), "var(--g500)")
        deliverables = c.bullets(m.get("deliverables") or [])
        owner_html = f'<div style="{owner_style}">{c.esc(m.get("owner"))}</div>' if m.get("owner") else ""
        ms_rows.append(
            f'<div style="display:grid;grid-template-columns:140px 14px 1fr;gap:18px;padding:14px 0;border-bottom:1px solid var(--g150);">'
            f'<div><div style="font-family:var(--mono);font-size:12px;color:var(--g500);">{c.esc(m.get("when"))}</div>'
            f'{(c.badge(m.get("status","next").upper(), kind="info") if m.get("status") else "")}</div>'
            f'<div><div style="width:10px;height:10px;border-radius:50%;background:{sc};margin-top:6px;"></div></div>'
            f'<div><h3 style="margin-bottom:6px;">{c.esc(m.get("name"))}</h3>'
            f'{owner_html}'
            f'{deliverables}</div>'
            f'</div>'
        )
    milestones_html = c.section("Milestones", body="".join(ms_rows)) if ms_rows else ""

    # Risks table
    risks = spec.get("risks") or []
    risks_html = ""
    if risks:
        rows = [[r.get("risk"),
                 c.raw(c.badge((r.get("likelihood") or "med").upper(), "warn")),
                 c.raw(c.badge((r.get("impact") or "med").upper(), "err")),
                 r.get("mitigation")] for r in risks]
        risks_html = c.section("Risks", body=c.table(["Risk", "Likelihood", "Impact", "Mitigation"], rows))

    # Data flow boxes
    flow = spec.get("data_flow") or []
    flow_html = ""
    if flow:
        boxes = []
        for i, step in enumerate(flow):
            boxes.append(f'<div class="flow-box">{c.esc(step)}</div>')
            if i < len(flow) - 1:
                boxes.append('<div class="flow-arrow">→</div>')
        flow_html = c.section("Data flow",
            body=f'<div class="flow-row">{"".join(boxes)}</div>')

    summary_html = spec.get("summary_html") or ""
    body = ((f'<section>{summary_html}</section>' if summary_html else "")
            + flow_html + milestones_html + risks_html)

    extra_css = """
    .flow-row { display:flex; align-items:center; gap:14px; flex-wrap:wrap; }
    .flow-box { background:var(--paper); border:var(--border); border-radius:var(--radius);
                padding:14px 18px; font-family:var(--mono); font-size:13px; min-width:120px;
                text-align:center; }
    .flow-arrow { color:var(--clay); font-size:24px; font-weight:700; }
    """
    return {
        "title": spec.get("title", "Implementation plan"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "PLAN"),
        "body": body,
        "extra_css": extra_css,
    }
