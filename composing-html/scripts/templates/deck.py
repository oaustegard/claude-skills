"""Slide deck template — arrow-key navigable single-file presentation.

  - deck.slide_deck: Title slide + content slides + optional code/quote slides.
"""

from __future__ import annotations

from . import register
import composer as c


_SLIDE_KINDS = {"title", "section", "content", "quote", "code", "image"}


def _render_slide(s: dict) -> str:
    kind = s.get("kind", "content")
    invert_class = " invert" if s.get("invert") else ""
    inner = ""
    if kind == "title":
        eb  = f'<div class="eyebrow">{c.esc(s.get("eyebrow",""))}</div>' if s.get("eyebrow") else ""
        sub = f'<p class="subtitle">{c.esc(s.get("subtitle",""))}</p>' if s.get("subtitle") else ""
        byl = f'<div class="byline">{c.esc(s.get("byline",""))}</div>' if s.get("byline") else ""
        inner = f'{eb}<h1>{c.esc(s.get("title",""))}</h1>{sub}{byl}'
    elif kind == "section":
        inner = f'<div class="eyebrow">{c.esc(s.get("eyebrow","SECTION"))}</div><h1>{c.esc(s.get("title",""))}</h1>'
    elif kind == "quote":
        attr = f'<div class="byline">— {c.esc(s.get("attribution",""))}</div>' if s.get("attribution") else ""
        inner = f'<blockquote style="font-family:var(--serif);font-size:34px;line-height:1.2;border-left:3px solid var(--clay);padding-left:24px;">{c.esc(s.get("quote",""))}</blockquote>{attr}'
    elif kind == "code":
        eb = f'<div class="eyebrow">{c.esc(s.get("eyebrow",""))}</div>' if s.get("eyebrow") else ""
        h  = f'<h2>{c.esc(s.get("title",""))}</h2>' if s.get("title") else ""
        inner = f'{eb}{h}{c.code_block(s.get("code",""), lang=s.get("lang"))}'
    elif kind == "image":
        cap = f'<div style="font-size:13px;color:var(--g500);margin-top:10px;text-align:center;">{c.esc(s.get("caption",""))}</div>' if s.get("caption") else ""
        inner = f'<img src="{c.esc(s.get("src",""))}" alt="{c.esc(s.get("alt",""))}" style="max-height:60vh;margin:0 auto;">{cap}'
    else:  # content
        eb = f'<div class="eyebrow">{c.esc(s.get("eyebrow",""))}</div>' if s.get("eyebrow") else ""
        h  = f'<h2>{c.esc(s.get("title",""))}</h2>' if s.get("title") else ""
        inner = f'{eb}{h}{s.get("body_html","")}'
    return f'<section class="slide{invert_class}"><div class="slide-inner">{inner}</div></section>'


@register(
    "deck.slide_deck",
    summary="Single-file slide deck with arrow-key/space navigation. Snap-scrolling.",
    spec_keys={
        "title": "Page title (also used as title slide if no title-kind slide present).",
        "subtitle": "Optional sub-headline used by an auto-title-slide.",
        "slides": "List[{kind: 'title|section|content|quote|code|image', invert?: bool, ...kind-specific keys}]. "
                  "title:{title,subtitle?,eyebrow?,byline?}. section:{title,eyebrow?}. "
                  "content:{title?,eyebrow?,body_html}. quote:{quote,attribution?}. "
                  "code:{title?,eyebrow?,code,lang?}. image:{src,alt?,caption?}.",
    },
)
def slide_deck(spec: dict) -> dict:
    slides = spec.get("slides") or []
    # If no title-kind slide, prepend one from title/subtitle.
    if not any(s.get("kind") == "title" for s in slides):
        slides = [{"kind": "title", "title": spec.get("title", "Untitled"), "subtitle": spec.get("subtitle", "")}] + slides
    body = "".join(_render_slide(s) for s in slides if s.get("kind") in _SLIDE_KINDS)
    extra_css = """
    body { scroll-snap-type: y mandatory; overflow-x: hidden; }
    main.page { max-width: none; padding: 0; }
    .colophon { display: none; }
    .slide { width: 100vw; min-height: 100vh; scroll-snap-align: start; scroll-snap-stop: always;
             display: flex; align-items: center; justify-content: center; padding: 8vh 6vw; }
    .slide-inner { width: 100%; max-width: 880px; }
    .slide.invert { background: var(--slate); color: var(--ivory); }
    .slide.invert .eyebrow { color: var(--g300); }
    .slide.invert .eyebrow::before { background: var(--clay); }
    .slide h1 { font-size: clamp(40px, 6vw, 64px); }
    .slide h2 { font-size: clamp(30px, 4vw, 42px); margin-bottom: 36px; }
    .slide pre { font-size: 16px; }
    .byline { margin-top: 40px; font-family: var(--mono); font-size: 12px; color: var(--g500); }
    """
    return {
        "title": spec.get("title", "Deck"),
        "subtitle": spec.get("subtitle"),
        "body": body,
        "show_masthead": False,
        "extra_css": extra_css,
        "body_attrs": {"data-deck": "true"},
    }
