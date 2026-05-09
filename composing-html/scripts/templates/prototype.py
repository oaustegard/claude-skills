"""Prototype templates.

  - prototype.animation_sandbox: Interactive parameter knobs that drive a
    visual element via CSS variables.
  - prototype.click_flow: Sequence of mockup screens with arrow links.
"""

from __future__ import annotations

from . import register
import composer as c


# --------------------------------------------------------------------------- #
# animation_sandbox                                                           #
# --------------------------------------------------------------------------- #

@register(
    "prototype.animation_sandbox",
    summary="Live-tunable parameters (sliders/selects) driving a CSS-variable preview.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "intro_html": "Optional intro HTML.",
        "params": "List[{name, label, type: 'range|select', min?, max?, step?, default, unit?, options?: [str], format?: 'number|percent|ms'}]. "
                  "Param values are exposed as CSS vars `--bind-<name>` and live-rendered via base.js.",
        "preview_html": "HTML for the preview region. Use the CSS vars `--bind-<name>` to react to params.",
        "preview_height": "Optional CSS height for preview region (default: '320px').",
    },
)
def animation_sandbox(spec: dict) -> dict:
    controls = []
    for p in spec.get("params", []):
        name = p["name"]
        label = c.esc(p.get("label", name))
        if p.get("type") == "select":
            opts = "".join(f'<option value="{c.esc(o)}">{c.esc(o)}</option>' for o in p.get("options", []))
            ctl = (f'<select data-bind="{c.esc(name)}" data-format="{c.esc(p.get("format",""))}">{opts}</select>')
        else:
            ctl = (f'<input type="range" data-bind="{c.esc(name)}" '
                   f'min="{p.get("min", 0)}" max="{p.get("max", 100)}" step="{p.get("step", 1)}" '
                   f'value="{p.get("default", 0)}" '
                   f'data-format="{c.esc(p.get("format",""))}" '
                   f'data-unit="{c.esc(p.get("unit",""))}">')
        controls.append(
            f'<div class="ctrl">'
            f'<div class="ctrl-row"><label>{label}</label>'
            f'<span class="ctrl-val" data-out="{c.esc(name)}"></span></div>'
            f'{ctl}</div>'
        )
    preview_h = c.esc(spec.get("preview_height", "320px"))
    body = ((f'<section>{spec.get("intro_html")}</section>' if spec.get("intro_html") else "")
            + c.section(body=(
                f'<div class="sandbox">'
                f'<div class="sandbox-preview" style="height:{preview_h};">{spec.get("preview_html","")}</div>'
                f'<div class="sandbox-controls">{"".join(controls)}</div>'
                f'</div>'
            )))
    extra_css = """
    .sandbox { display: grid; grid-template-columns: 1fr 280px; gap: 24px; }
    @media (max-width: 880px) { .sandbox { grid-template-columns: 1fr; } }
    .sandbox-preview { background: var(--paper); border: var(--border); border-radius: var(--radius);
                       display: flex; align-items: center; justify-content: center; overflow: hidden; }
    .sandbox-controls { display: flex; flex-direction: column; gap: 18px;
                        background: var(--g100); border: var(--border-soft); border-radius: var(--radius);
                        padding: 20px; }
    .ctrl-row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
    .ctrl-row label { font-family: var(--mono); font-size: 12px; color: var(--g700); }
    .ctrl-val { font-family: var(--mono); font-size: 12px; color: var(--clay-d); }
    .ctrl input[type="range"], .ctrl select { width: 100%; }
    """
    return {
        "title": spec.get("title", "Prototype"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "PROTOTYPE"),
        "body": body,
        "extra_css": extra_css,
    }


# --------------------------------------------------------------------------- #
# click_flow                                                                  #
# --------------------------------------------------------------------------- #

@register(
    "prototype.click_flow",
    summary="Sequence of mockup screens connected by labelled arrows.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "screens": "List[{id, label, html, transitions?: [{label, to_id}]}].",
    },
)
def click_flow(spec: dict) -> dict:
    screens = spec.get("screens") or []
    cards = []
    for s in screens:
        trs = ""
        if s.get("transitions"):
            chips = " ".join(
                f'<a href="#{c.esc(t["to_id"])}" class="tr">{c.esc(t.get("label","→"))}</a>'
                for t in s["transitions"]
            )
            trs = f'<div class="screen-tr">{chips}</div>'
        cards.append(
            f'<div class="screen" id="{c.esc(s.get("id"))}">'
            f'<div class="screen-head">{c.esc(s.get("label"))}</div>'
            f'<div class="screen-body">{s.get("html","")}</div>'
            f'{trs}</div>'
        )
    body = c.section(body=f'<div class="flow-grid">{"".join(cards)}</div>')
    extra_css = """
    .flow-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px; }
    .screen { display: flex; flex-direction: column; background: var(--paper); border: var(--border);
              border-radius: var(--radius); overflow: hidden; }
    .screen-head { padding: 10px 14px; background: var(--g100); font-family: var(--mono); font-size: 12px; color: var(--g500); }
    .screen-body { padding: 16px; flex: 1; min-height: 200px; }
    .screen-tr { padding: 10px 14px; border-top: 1px solid var(--g150); display: flex; gap: 8px; flex-wrap: wrap; }
    .tr { background: var(--oat); color: var(--clay-d); font-family: var(--mono); font-size: 11px;
          padding: 4px 10px; border-radius: 999px; text-decoration: none; }
    .tr:hover { background: var(--clay); color: white; }
    """
    return {
        "title": spec.get("title", "Click flow"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "PROTOTYPE"),
        "body": body,
        "extra_css": extra_css,
        "page_class": "page page--wide",
    }
