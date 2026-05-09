"""Smoke + regression tests for composing-html.

Run with:  python -m pytest composing-html/tests -q
        or python composing-html/tests/test_smoke.py        (no pytest needed)

Covers every template builder with a representative spec, then asserts each
output:
  - starts with `<!doctype html>`
  - parses cleanly with html.parser
  - contains the expected content marker
  - does NOT contain raw `<script>alert` or `<img onerror=` injections from
    spec-side strings (regression for the deleted `_looks_like_html` heuristic)
"""

from __future__ import annotations

import html.parser as hp
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import composer as c                       # noqa: E402
from composer import page, raw, table, callout, css_color, esc  # noqa: E402
from templates import REGISTRY             # noqa: E402


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #

def _parses(html_str: str) -> bool:
    try:
        hp.HTMLParser().feed(html_str); return True
    except Exception:
        return False


def _build(name: str, spec: dict) -> str:
    assert name in REGISTRY, f"template {name!r} not registered"
    return page(**REGISTRY[name]["build"](spec))


# --------------------------------------------------------------------------- #
# representative specs (exercise the interesting branches of each template)   #
# --------------------------------------------------------------------------- #

SPECS: dict[str, dict] = {
    "freeform": {
        "title": "ff", "body_html": "<section><h2>Hi</h2><p>x</p></section>",
    },
    "exploration.comparison_grid": {
        "title": "Compare", "recommendation": "A",
        "options": [
            {"name": "A", "verdict": "best", "summary": "s",
             "pros": ["p1"], "cons": ["c1"], "tags": ["t"]},
            {"name": "B", "summary": "s2"},
        ],
    },
    "exploration.design_directions": {
        "title": "Dir",
        "directions": [
            {"name": "D1", "vibe": "v", "palette": ["#FAF9F5", "#D97757"],
             "typography": {"display": "Aa", "body": "x"}, "notes": "n"},
        ],
    },
    "exploration.implementation_plan": {
        "title": "Plan", "data_flow": ["A", "B"],
        "milestones": [
            {"name": "m", "when": "wk1", "owner": "alex",
             "status": "active", "deliverables": ["d"]}],
        "risks": [{"risk": "r", "likelihood": "med", "impact": "high",
                   "mitigation": "m"}],
    },
    "review.pr_review": {
        "title": "PR", "pr": {"repo": "r", "number": 1, "branch": "b",
                              "author": "a", "additions": 1, "deletions": 1},
        "verdict": "approve", "summary_html": "<p>s</p>",
        "findings": [{"file": "x.py", "line": 1, "severity": "warn",
                      "title": "t", "body_html": "<p>b</p>",
                      "snippet": "x = 1", "snippet_lang": "python"}],
    },
    "review.code_walkthrough": {
        "title": "Walk",
        "steps": [{"heading": "h", "body_html": "<p>b</p>", "code": "x=1", "lang": "python"}],
    },
    "review.module_map": {
        "title": "Map",
        "nodes": [{"id": "a", "label": "A", "kind": "core"},
                  {"id": "b", "label": "B", "kind": "util"}],
        "edges": [{"from": "a", "to": "b", "label": "calls"}],
        "legend": [{"label": "core", "kind": "core"}],
    },
    "design.design_system": {
        "title": "DS",
        "colors": {"Brand": [{"name": "Clay", "hex": "#D97757", "token": "--clay"}]},
        "typography": [{"name": "Body", "font_family": "var(--sans)", "size": "16px", "weight": "400"}],
        "spacing": [{"name": "sm", "px": 8}],
        "radii": [{"name": "sm", "px": 4}],
    },
    "design.component_variants": {
        "title": "CV",
        "components": [{
            "name": "Button",
            "axes": {"Size": ["sm", "md"], "Intent": ["primary"]},
            "cells": [{"coords": {"Size": "sm", "Intent": "primary"}, "html": "<button>x</button>"}],
        }],
    },
    "prototype.animation_sandbox": {
        "title": "Sandbox",
        "params": [{"name": "d", "label": "Dur", "type": "range",
                    "min": 0, "max": 1000, "default": 300, "unit": "ms"}],
        "preview_html": "<div></div>",
    },
    "prototype.click_flow": {
        "title": "Flow",
        "screens": [
            {"id": "a", "label": "A", "html": "<p>A</p>",
             "transitions": [{"label": "→", "to_id": "b"}]},
            {"id": "b", "label": "B", "html": "<p>B</p>"},
        ],
    },
    "diagram.svg_figure_sheet": {
        "title": "Figs",
        "figures": [{"label": "F1", "caption": "c",
                     "svg": "<svg viewBox='0 0 10 10'><rect width='10' height='10'/></svg>"}],
    },
    "diagram.flowchart": {
        "title": "Flow", "orientation": "vertical",
        "steps": [{"id": "s1", "label": "Start", "kind": "start"},
                  {"id": "s2", "label": "End",   "kind": "end"}],
    },
    "deck.slide_deck": {
        "title": "Deck",
        "slides": [{"kind": "title", "title": "T"},
                   {"kind": "content", "title": "C", "body_html": "<p>x</p>"}],
    },
    "research.feature_explainer": {
        "title": "Feat",
        "sections": [{"id": "a", "heading": "A", "body_html": "<p>x</p>",
                      "code_tabs": [{"label": "py", "code": "x=1", "lang": "python"}]}],
    },
    "research.concept_explainer": {
        "title": "Concept", "body_html": "<p>x</p>",
        "glossary": [{"term": "t", "definition_html": "<code>v</code>"}],
    },
    "report.status_report": {
        "title": "Status",
        "metrics": [{"label": "X", "value": "1", "delta": "+1", "kind": "ok"}],
        "shipped": [{"title": "s", "owner": "o"}],
        "in_flight": [{"title": "i", "progress": 0.5}],
        "blocked": [{"title": "b"}],
    },
    "report.incident_report": {
        "title": "INC", "severity": "sev2", "duration": "30m",
        "impact_html": "<p>i</p>", "summary_html": "<p>s</p>",
        "timeline": [{"at": "14:00", "event": "e", "kind": "detected"}],
        "root_cause_html": "<p>rc</p>",
        "followups": [{"title": "f", "owner": "o", "due": "d", "status": "open"}],
    },
    "editor.triage_board": {
        "title": "Board",
        "columns": [{"id": "todo", "label": "Todo", "color": "info",
                     "items": [{"id": "i1", "title": "x", "tags": ["P1"]}]}],
    },
    "editor.flag_editor": {
        "title": "Flags",
        "flags": [{"id": "a", "label": "A", "default": True},
                  {"id": "b", "label": "B", "default": False, "requires": ["a"]}],
    },
    "editor.prompt_tuner": {
        "title": "Tuner", "template": "Hi {{name}}",
        "variables": [{"name": "name", "default": "x"}],
    },
}


# --------------------------------------------------------------------------- #
# tests                                                                       #
# --------------------------------------------------------------------------- #

def test_every_template_has_a_spec():
    missing = sorted(set(REGISTRY) - set(SPECS))
    assert not missing, f"specs missing for: {missing}"


def test_every_template_renders_and_parses():
    failures = []
    for name, spec in SPECS.items():
        try:
            html = _build(name, spec)
            assert html.startswith("<!doctype html>"), f"{name}: no doctype"
            assert "</html>" in html, f"{name}: no </html>"
            assert _parses(html), f"{name}: parser raised"
        except Exception as e:
            failures.append((name, str(e)))
    assert not failures, "\n".join(f"{n}: {e}" for n, e in failures)


# --- security regressions ------------------------------------------------- #

INJECT = "<script>alert(1)</script><img src=x onerror=alert(1)>"


def test_table_does_not_emit_raw_script():
    out = table(["x"], [[INJECT]])
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_callout_escapes_plain_strings():
    out = callout(INJECT)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_table_raw_opt_in_works():
    out = table(["x"], [[raw("<b>ok</b>")]])
    assert "<b>ok</b>" in out


def test_implementation_plan_owner_attr_is_quoted():
    out = _build("exploration.implementation_plan", {
        "title": "p",
        "milestones": [{"name": "m", "when": "wk1", "owner": "alex",
                        "deliverables": ["d"]}],
    })
    # Owner div must use a quoted style attribute, not `style=font-...`.
    assert 'style="font-family:var(--mono)' in out
    assert 'style=font-family' not in out


def test_prompt_tuner_defends_against_script_breakout():
    out = _build("editor.prompt_tuner", {
        "title": "x",
        "template": "before </script><img src=x onerror=alert(1)> after",
        "variables": [{"name": "x", "default": ""}],
    })
    # Inside the inlined JS string literal, </ must be escaped to <\/.
    # The plain literal `</script>` must not appear except as the closing tag
    # of the actual <script> we emit ourselves.
    closing_tags = out.count("</script>")
    assert closing_tags == 1, (
        f"expected exactly one </script> (the real closer); found {closing_tags}"
    )


def test_flag_editor_escapes_id_in_attrs():
    out = _build("editor.flag_editor", {
        "title": "f",
        "flags": [{"id": 'a"b', "label": "L", "default": True,
                   "requires": ['x"y']}],
    })
    # The injected " must be HTML-escaped inside both the data-id and
    # data-requires attributes; the surrounding attribute uses double quotes.
    assert 'data-id="a&quot;b"' in out
    assert "&quot;" in out  # JSON " inside data-requires is escaped


def test_flag_editor_handles_missing_id():
    out = _build("editor.flag_editor", {
        "title": "f",
        "flags": [{"label": "no-id", "default": False}],
    })
    assert "</html>" in out  # no KeyError


def test_module_map_does_not_mutate_spec():
    spec = {"nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "edges": [{"from": "a", "to": "b"}]}
    snap = json.dumps(spec, sort_keys=True)
    _build("review.module_map", spec)
    assert json.dumps(spec, sort_keys=True) == snap, (
        "module_map mutated the caller's spec — nodes still hold injected x/y"
    )


def test_module_map_warns_on_unknown_edge(capsys):
    spec = {"nodes": [{"id": "a", "label": "A"}],
            "edges": [{"from": "a", "to": "missing"}]}
    _build("review.module_map", spec)
    err = capsys.readouterr().err
    assert "unknown id" in err or "missing" in err


def test_slide_deck_raises_on_unknown_kind():
    try:
        _build("deck.slide_deck", {"slides": [{"kind": "contant", "title": "x"}]})
    except ValueError as e:
        assert "unknown slide kind" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_css_color_rejects_injection():
    assert css_color("#D97757") == "#D97757"
    assert css_color("var(--clay)") == "var(--clay)"
    assert css_color("rgb(217,119,87)") == "rgb(217,119,87)"
    assert css_color("red;background-image:url(http://x)") != "red;background-image:url(http://x)"
    assert css_color("javascript:alert(1)") != "javascript:alert(1)"
    assert css_color("transparent") == "transparent"


def test_describe_emits_valid_json():
    """Regression for #8 — the printed skeleton must round-trip via json.loads."""
    import re
    import build as _build_mod
    import io, contextlib

    class _Args:
        pass
    for name in REGISTRY:
        a = _Args(); a.template = name
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _build_mod.cmd_describe(a)
        out = buf.getvalue()
        m = re.search(r"```json\n(.*?)\n```", out, re.DOTALL)
        assert m, f"{name}: no JSON block in describe output"
        json.loads(m.group(1))  # raises if invalid


# --------------------------------------------------------------------------- #
# direct entrypoint                                                           #
# --------------------------------------------------------------------------- #

def _run_directly() -> int:
    """Plain runner so the suite works without pytest installed."""
    failed = 0
    fns = [v for k, v in globals().items() if k.startswith("test_") and isinstance(v, types.FunctionType)]
    for fn in fns:
        # Stub `capsys` for the one test that uses it.
        import io, sys as _sys
        if "capsys" in fn.__code__.co_varnames:
            buf_err = io.StringIO()
            old_err = _sys.stderr
            _sys.stderr = buf_err
            try:
                class _CS:  # minimal capsys stand-in
                    def readouterr(self_inner):
                        return types.SimpleNamespace(out="", err=buf_err.getvalue())
                fn(_CS())
                print(f"  ✓ {fn.__name__}")
            except AssertionError as e:
                failed += 1; print(f"  ✗ {fn.__name__}: {e}")
            finally:
                _sys.stderr = old_err
        else:
            try:
                fn(); print(f"  ✓ {fn.__name__}")
            except AssertionError as e:
                failed += 1; print(f"  ✗ {fn.__name__}: {e}")
            except Exception as e:
                failed += 1; print(f"  ✗ {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_directly())
