"""Tests for composing-html's deterministic checker.

Run with:  python composing-html/tests/test_checker.py    (no pytest needed)
       or  python -m pytest composing-html/tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from checker import check_html, has_errors  # noqa: E402


def _rules(html, **kw):
    return {f.rule for f in check_html(html, **kw)}


_PASS = 0
_FAIL = 0


def ok(cond, label):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
        print(f"  FAIL: {label}")


# --- clean fragment: no findings ------------------------------------------- #
clean = """
<section>
  <div class="eyebrow">OVERVIEW</div>
  <h2>Status</h2>
  <div class="grid grid--2">
    <div class="card"><p style="color: var(--clay)">All good</p></div>
    <div class="card"><span class="badge badge--ok">v1</span></div>
  </div>
  <img src="x.png" alt="diagram">
</section>
"""
ok(_rules(clean, fragment=True) == set(), "clean fragment yields no findings")
ok(not has_errors(check_html(clean, fragment=True)), "clean fragment has no errors")

# --- chrome leak (fragment only) ------------------------------------------- #
ok("chrome-leak" in _rules('<head><link rel="x"></head><p>hi</p>', fragment=True),
   "chrome-leak fires on <head>/<link> in fragment")
ok("chrome-leak" not in _rules('<!doctype html><html><head></head><body>x</body></html>'),
   "chrome-leak silent on a full artifact")

# --- undefined token ------------------------------------------------------- #
ok("undefined-token" in _rules('<p style="color: var(--cley)">typo</p>', fragment=True),
   "undefined-token catches var(--cley) typo")
ok("undefined-token" not in _rules('<p style="color: var(--clay)">ok</p>', fragment=True),
   "undefined-token silent on valid token")
ok("undefined-token" not in _rules(
       '<input data-bind="size"><span style="width: var(--bind-size)"></span>', fragment=True),
   "undefined-token silent on --bind-* created by data-bind")
ok("undefined-token" not in _rules(
       '<div style="--mytok: 4px; padding: var(--mytok)"></div>', fragment=True),
   "undefined-token silent on author-declared custom property")

# --- hardcoded colour ------------------------------------------------------ #
ok("hardcoded-color" in _rules('<p style="color:#ff0000">red</p>', fragment=True),
   "hardcoded-color catches hex literal")
ok("hardcoded-color" in _rules('<p style="background: rgb(1,2,3)">x</p>', fragment=True),
   "hardcoded-color catches rgb()")

# --- inline typography ----------------------------------------------------- #
ok("inline-typography" in _rules('<p style="font-family: Inter">x</p>', fragment=True),
   "inline-typography catches font-family")
ok("inline-typography" in _rules('<p style="font-size: 22px">x</p>', fragment=True),
   "inline-typography catches font-size")

# --- nested card ----------------------------------------------------------- #
ok("nested-card" in _rules('<div class="card"><div class="card">x</div></div>', fragment=True),
   "nested-card catches card-in-card")
ok("nested-card" not in _rules('<div class="card">x</div><div class="card">y</div>', fragment=True),
   "nested-card silent on sibling cards")
ok("nested-card" not in _rules('<div class="scorecard"><div class="card">x</div></div>', fragment=True),
   "nested-card does not match substring 'scorecard'")

# --- broken tabs ----------------------------------------------------------- #
broken_tabs = '<div class="tabs"><button data-target="a">A</button></div>'
ok("broken-tabs" in _rules(broken_tabs, fragment=True),
   "broken-tabs catches target with no panel")
good_tabs = ('<div class="tabs"><button data-target="a">A</button></div>'
             '<div class="tab-panel" data-id="a">x</div>')
ok("broken-tabs" not in _rules(good_tabs, fragment=True),
   "broken-tabs silent on wired tabs")

# --- broken bind ----------------------------------------------------------- #
ok("broken-bind" in _rules('<input data-bind="size">', fragment=True),
   "broken-bind catches bind with no consumer")
ok("broken-bind" in _rules('<span data-out="ghost"></span>', fragment=True),
   "broken-bind catches orphan data-out")

# --- broken sortable ------------------------------------------------------- #
ok("broken-sortable" in _rules('<div data-sortable="true"><div>x</div></div>', fragment=True),
   "broken-sortable catches no draggable children")
ok("broken-sortable" not in _rules(
       '<div data-sortable="true"><div draggable="true">x</div></div>', fragment=True),
   "broken-sortable silent when draggable present")

# --- heading skip ---------------------------------------------------------- #
ok("heading-skip" in _rules('<h1>a</h1><h3>b</h3>', fragment=True),
   "heading-skip catches h1->h3")
ok("heading-skip" not in _rules('<h1>a</h1><h2>b</h2><h3>c</h3>', fragment=True),
   "heading-skip silent on proper nesting")

# --- img no alt ------------------------------------------------------------ #
ok("img-no-alt" in _rules('<img src="x.png">', fragment=True),
   "img-no-alt catches missing alt")
ok("img-no-alt" not in _rules('<img src="x.png" alt="">', fragment=True),
   "img-no-alt silent on empty alt")

# --- severity contract ----------------------------------------------------- #
ok(has_errors(check_html('<p style="color: var(--nope)">x</p>', fragment=True)),
   "undefined-token is error severity")
ok(not has_errors(check_html('<img src=x>', fragment=True)),
   "img-no-alt alone is not error severity")


print(f"\n{_PASS} passed, {_FAIL} failed")
sys.exit(1 if _FAIL else 0)
