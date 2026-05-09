"""freeform — minimal shell, Claude provides arbitrary inner HTML.

Use when no other template fits. Page chrome (head, css, js, masthead,
colophon) is composed by the shell; only the body content is the
caller's responsibility.
"""

from __future__ import annotations

from . import register
import composer as c


@register("freeform", summary="Base shell with caller-supplied inner HTML.",
          spec_keys={
              "title": "Page title (string).",
              "subtitle": "Optional sub-headline shown under the title.",
              "eyebrow": "Optional small all-caps label above the title.",
              "body_html": "Raw HTML for the page body. May use any class from base.css.",
              "extra_css": "Optional extra CSS injected into <style> after base.css.",
              "extra_js": "Optional extra JS appended after base.js.",
              "page_class": "Optional layout: 'page', 'page page--wide', 'page page--narrow'.",
              "show_masthead": "Bool, default true. Set false to omit the title block entirely.",
              "body_attrs": "Optional dict of attrs on <body> (e.g. {'data-deck': 'true'}).",
          })
def build(spec: dict) -> dict:
    return {
        "title":          spec.get("title", "Untitled"),
        "subtitle":       spec.get("subtitle"),
        "eyebrow_text":   spec.get("eyebrow"),
        "body":           spec.get("body_html", ""),
        "extra_css":      spec.get("extra_css", ""),
        "extra_js":       spec.get("extra_js", ""),
        "page_class":     spec.get("page_class", "page"),
        "show_masthead":  spec.get("show_masthead", True),
        "body_attrs":     spec.get("body_attrs"),
    }
