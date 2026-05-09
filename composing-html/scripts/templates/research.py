"""Research & learning templates.

  - research.feature_explainer: Tabbed walkthrough with code samples and a TOC.
  - research.concept_explainer: Inline concept doc with collapsibles + glossary.
"""

from __future__ import annotations

from . import register
import composer as c


# --------------------------------------------------------------------------- #
# feature_explainer                                                           #
# --------------------------------------------------------------------------- #

@register(
    "research.feature_explainer",
    summary="Feature explainer: TOC + sections + tabbed code samples per section.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "intro_html": "Optional intro HTML.",
        "sections": "List[{id, heading, body_html, code_tabs?: [{label, code, lang?}]}].",
    },
)
def feature_explainer(spec: dict) -> dict:
    secs = spec.get("sections") or []
    toc_links = "".join(f'<a href="#{c.esc(s.get("id"))}">{c.esc(s.get("heading"))}</a>' for s in secs)
    toc_html = (f'<aside class="toc"><div class="toc-label">CONTENTS</div>{toc_links}</aside>'
                if toc_links else "")
    parts = []
    for s in secs:
        tabs_html = ""
        if s.get("code_tabs"):
            panels = [{"id": f'{s.get("id","s")}-{i}',
                       "label": t.get("label", f"Sample {i+1}"),
                       "html": c.code_block(t.get("code",""), lang=t.get("lang"))}
                      for i, t in enumerate(s["code_tabs"])]
            tabs_html = c.tabs(panels)
        parts.append(
            f'<section id="{c.esc(s.get("id"))}"><h2>{c.esc(s.get("heading"))}</h2><hr class="rule">'
            f'<div>{s.get("body_html","")}</div>'
            + (f'<div style="margin-top:18px;">{tabs_html}</div>' if tabs_html else "")
            + '</section>'
        )
    body = (f'<div class="explainer">'
            f'{toc_html}'
            f'<div class="explainer-body">'
            + (f'<section>{spec.get("intro_html")}</section>' if spec.get("intro_html") else "")
            + "".join(parts) + '</div></div>')
    extra_css = """
    .explainer { display: grid; grid-template-columns: 200px 1fr; gap: 48px; align-items: start; }
    @media (max-width: 880px) { .explainer { grid-template-columns: 1fr; } .toc { position: static !important; } }
    .toc { position: sticky; top: 24px; display: flex; flex-direction: column; gap: 4px; }
    .toc-label { font-family: var(--mono); font-size: 11px; letter-spacing: .08em; color: var(--g500); margin-bottom: 8px; }
    .toc a { font-size: 14px; color: var(--g700); padding: 4px 0; text-decoration: none; border-left: 2px solid var(--g200); padding-left: 12px; }
    .toc a:hover { color: var(--clay-d); border-left-color: var(--clay); }
    """
    return {
        "title": spec.get("title", "Feature"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "EXPLAINER"),
        "body": body,
        "extra_css": extra_css,
        "page_class": "page page--wide",
    }


# --------------------------------------------------------------------------- #
# concept_explainer                                                           #
# --------------------------------------------------------------------------- #

@register(
    "research.concept_explainer",
    summary="Concept explainer: prose + interactive demo slot + glossary.",
    spec_keys={
        "title": "Page title.",
        "subtitle": "Optional sub-headline.",
        "body_html": "Main concept body HTML (use <h2>, <p>, <details>, etc).",
        "demo_html": "Optional HTML for an embedded demo region.",
        "glossary": "Optional list[{term, definition_html}].",
    },
)
def concept_explainer(spec: dict) -> dict:
    demo = ""
    if spec.get("demo_html"):
        demo = c.section("Demo", body=c.card(spec["demo_html"], elev=True))
    glossary = ""
    if spec.get("glossary"):
        rows = "".join(
            f'<div style="display:grid;grid-template-columns:160px 1fr;gap:16px;padding:12px 0;border-bottom:1px solid var(--g150);">'
            f'<div style="font-family:var(--mono);font-size:13px;color:var(--clay-d);">{c.esc(g.get("term"))}</div>'
            f'<div>{g.get("definition_html","")}</div></div>'
            for g in spec["glossary"]
        )
        glossary = c.section("Glossary", body=f'<div>{rows}</div>')
    body = (f'<section>{spec.get("body_html","")}</section>{demo}{glossary}')
    return {
        "title": spec.get("title", "Concept"),
        "subtitle": spec.get("subtitle"),
        "eyebrow_text": spec.get("eyebrow", "CONCEPT"),
        "body": body,
        "page_class": "page page--narrow",
    }
