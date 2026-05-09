"""composing-html / composer.py

Page shell + primitive helpers shared by every template module.

Templates receive a structured spec (a dict) and return a single HTML string
that goes into <body>. The composer wraps it with <head>, inlines base.css /
base.js, and adds the colophon footer. Templates never write <html>, <head>,
<style>, <script>, or <link>.

Helpers provided here are deliberately small. Each takes plain Python data
(strings, dicts, lists) and returns an HTML string. Nothing fancy — keep the
output readable when someone opens the file in DevTools.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Iterable

ASSETS = Path(__file__).resolve().parent.parent / "assets"


# --------------------------------------------------------------------------- #
# escaping                                                                    #
# --------------------------------------------------------------------------- #

def esc(value: Any) -> str:
    """Escape for text content. Lists are joined with spaces. None → ''."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(esc(v) for v in value)
    return html.escape(str(value), quote=True)


def attrs(mapping: dict | None) -> str:
    """Render a dict of attributes. Drops None / False; True → bare attr.

    Keys with underscores are translated to hyphens so Python kwargs like
    ``data_target`` become ``data-target``.
    """
    if not mapping:
        return ""
    parts = []
    for k, v in mapping.items():
        if v is None or v is False:
            continue
        key = k.replace("_", "-")
        if v is True:
            parts.append(key)
        else:
            parts.append(f'{key}="{html.escape(str(v), quote=True)}"')
    return (" " + " ".join(parts)) if parts else ""


# --------------------------------------------------------------------------- #
# primitives                                                                  #
# --------------------------------------------------------------------------- #

def tag(name: str, inner: str = "", **attributes: Any) -> str:
    return f"<{name}{attrs(attributes)}>{inner}</{name}>"


def void(name: str, **attributes: Any) -> str:
    return f"<{name}{attrs(attributes)}>"


def eyebrow(text: str) -> str:
    return f'<div class="eyebrow">{esc(text)}</div>' if text else ""


def badge(label: str, kind: str | None = None) -> str:
    cls = "badge" + (f" badge--{kind}" if kind else "")
    return f'<span class="{cls}">{esc(label)}</span>'


def kbd(key: str) -> str:
    return f'<span class="kbd">{esc(key)}</span>'


def code_block(source: str, lang: str | None = None) -> str:
    cls = f' class="lang-{esc(lang)}"' if lang else ""
    return f'<pre><code{cls}>{esc(source)}</code></pre>'


def inline_code(source: str) -> str:
    return f"<code>{esc(source)}</code>"


def section(title: str | None = None, body: str = "", id: str | None = None,
            wide: bool = False) -> str:
    head = ""
    if title:
        head = f'<h2>{esc(title)}</h2><hr class="rule">'
    sec_attrs = attrs({"id": id, "class": "wide" if wide else None})
    return f"<section{sec_attrs}>{head}{body}</section>"


def card(body: str, title: str | None = None, *, soft: bool = False,
         elev: bool = False, extra_class: str = "") -> str:
    classes = ["card"]
    if soft: classes.append("card--soft")
    if elev: classes.append("card--elev")
    if extra_class: classes.append(extra_class)
    head = f"<h3>{esc(title)}</h3>" if title else ""
    return f'<div class="{" ".join(classes)}">{head}{body}</div>'


def grid(items: Iterable[str], cols: int | str = "auto", gap: int = 20) -> str:
    cls = f"grid grid--{cols}"
    style = f"gap:{gap}px;"
    return f'<div class="{cls}" style="{style}">{"".join(items)}</div>'


def stack(items: Iterable[str], gap: int = 16) -> str:
    return f'<div class="stack" style="gap:{gap}px;">{"".join(items)}</div>'


def row(items: Iterable[str], gap: int = 12) -> str:
    return f'<div class="row" style="gap:{gap}px;">{"".join(items)}</div>'


def bullets(items: Iterable[str]) -> str:
    return '<ul class="bullets">' + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def kv_list(pairs: dict[str, Any]) -> str:
    """Definition-list-style key/value rendering."""
    rows = "".join(
        f'<div style="display:flex;gap:12px;padding:8px 0;border-bottom:1px solid var(--g150);">'
        f'<div style="font-family:var(--mono);font-size:12px;color:var(--g500);min-width:140px;">{esc(k)}</div>'
        f'<div>{esc(v)}</div></div>'
        for k, v in pairs.items()
    )
    return f'<div>{rows}</div>'


def raw(html_string: str) -> "_Raw":
    """Wrap a string to opt out of HTML escaping in `table` and `callout` cells.

    Use this when a cell genuinely needs to contain HTML markup the caller
    constructed (e.g. a `badge()` result). Plain strings are always escaped.
    """
    return _Raw(html_string)


class _Raw(str):
    """Marker subclass for opt-in raw HTML in cells. Treated as str everywhere
    except composer functions that switch on `isinstance(x, _Raw)`."""
    __slots__ = ()


def _cell(value: Any) -> str:
    return str(value) if isinstance(value, _Raw) else esc(value)


def table(columns: list[str], rows: list[list[Any]]) -> str:
    head = "<thead><tr>" + "".join(f"<th>{esc(c)}</th>" for c in columns) + "</tr></thead>"
    body = "<tbody>" + "".join(
        "<tr>" + "".join(f"<td>{_cell(cell)}</td>" for cell in r) + "</tr>"
        for r in rows
    ) + "</tbody>"
    return f"<table>{head}{body}</table>"


def details(summary: str, body: str, *, open: bool = False) -> str:
    return f'<details{" open" if open else ""}><summary>{esc(summary)}</summary>{body}</details>'


def tabs(panels: list[dict[str, Any]]) -> str:
    """panels: [{id, label, html}]"""
    btns = "".join(f'<button data-target="{esc(p["id"])}">{esc(p["label"])}</button>' for p in panels)
    body = "".join(f'<div class="tab-panel" data-id="{esc(p["id"])}">{p["html"]}</div>' for p in panels)
    return f'<div class="tabgroup"><div class="tabs">{btns}</div>{body}</div>'


def callout(text: Any, kind: str = "info", icon: str | None = None) -> str:
    """Render an info/ok/warn/err callout box. Pass `raw(html)` to opt out of escaping."""
    color = {"info": "var(--info)", "ok": "var(--ok)", "warn": "var(--warn)", "err": "var(--err)"}.get(kind, "var(--info)")
    bg    = {"info": "#DCE7EE", "ok": "#E8EFE0", "warn": "#F8ECCB", "err": "#F4DAD5"}.get(kind, "#DCE7EE")
    icon_html = f'<span style="font-weight:700;">{esc(icon)}</span>' if icon else ""
    return (f'<div style="border-left:3px solid {color};background:{bg};padding:12px 16px;'
            f'border-radius:0 var(--radius-sm) var(--radius-sm) 0;display:flex;gap:10px;align-items:flex-start;">'
            f'{icon_html}<div>{_cell(text)}</div></div>')


# --------------------------------------------------------------------------- #
# page shell                                                                  #
# --------------------------------------------------------------------------- #

def page(*, title: str, body: str,
         subtitle: str | None = None,
         eyebrow_text: str | None = None,
         page_class: str = "page",
         body_attrs: dict | None = None,
         extra_css: str = "",
         extra_js: str = "",
         show_masthead: bool = True,
         colophon: str | None = "Composed with composing-html") -> str:
    """Wrap inner body html with the full page shell.

    Inlines base.css and base.js so the artifact is a single, portable file.
    Templates can pass extra_css / extra_js for one-off rules.
    """
    base_css = (ASSETS / "base.css").read_text(encoding="utf-8")
    base_js  = (ASSETS / "base.js").read_text(encoding="utf-8")

    masthead_html = ""
    if show_masthead and (title or subtitle or eyebrow_text):
        parts = []
        if eyebrow_text:
            parts.append(f'<div class="eyebrow">{esc(eyebrow_text)}</div>')
        if title:
            parts.append(f'<h1>{esc(title)}</h1>')
        if subtitle:
            parts.append(f'<p class="subtitle">{esc(subtitle)}</p>')
        masthead_html = f'<header class="masthead">{"".join(parts)}</header>'

    colo_html = (f'<div class="colophon"><span>{esc(colophon)}</span>'
                 f'<span></span></div>') if colophon else ""

    body_attr_str = attrs(body_attrs)

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>{esc(title or "Untitled")}</title>\n'
        '<style>\n' + base_css + '\n'
        + (extra_css and ("\n/* template extras */\n" + extra_css + "\n") or "") +
        '</style>\n'
        '</head>\n'
        f'<body{body_attr_str}>\n'
        f'<main class="{page_class}">'
        f'{masthead_html}'
        f'{body}'
        f'{colo_html}'
        f'</main>\n'
        '<script>\n' + base_js + '\n'
        + (extra_js and ("\n/* template extras */\n" + extra_js + "\n") or "") +
        '</script>\n'
        '</body>\n'
        '</html>\n'
    )


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #

_CSS_COLOR_RE = re.compile(
    r"^("
    r"#[0-9a-fA-F]{3,8}"                  # hex
    r"|rgba?\([^)]+\)"                    # rgb / rgba
    r"|hsla?\([^)]+\)"                    # hsl / hsla
    r"|var\(--[a-zA-Z0-9_-]+(?:\s*,\s*[#a-zA-Z0-9.,()% _-]+)?\)"  # var(--token[, fallback])
    r"|[a-zA-Z]{3,30}"                    # named: 'red', 'transparent', 'currentColor'
    r")$"
)


def css_color(value: Any, default: str = "var(--g500)") -> str:
    """Whitelist a CSS color value. Anything that doesn't look like a color
    falls back to `default`. Use this for any color taken from a spec field."""
    if not isinstance(value, str):
        return default
    v = value.strip()
    return v if _CSS_COLOR_RE.match(v) else default


def slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(text)).strip("-").lower()
    return s or "x"


def json_dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
