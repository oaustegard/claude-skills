#!/usr/bin/env python3
"""Build a drag-to-bookmarks-bar page for the page-scrawl overlay.

Usage: python3 make_bookmarklet.py [output.html]

The bookmarklet lets the user open the markup overlay themselves, without asking
Claude first. Pages with a strict Content-Security-Policy may refuse to run it;
Claude in Chrome's javascript_tool is not affected by CSP.
"""
import html
import sys
from pathlib import Path
from urllib.parse import quote

here = Path(__file__).resolve().parent
src = (here / "overlay.js").read_text()
href = "javascript:" + quote(src + "\nvoid 0;", safe="")
out = Path(sys.argv[1] if len(sys.argv) > 1 else "page-scrawl-bookmarklet.html")
out.write_text(f"""<!doctype html>
<meta charset="utf-8">
<title>page-scrawl bookmarklet</title>
<style>
  body {{ font: 15px/1.5 system-ui, sans-serif; max-width: 560px; margin: 60px auto; padding: 0 16px; color: #111; background: #fff; }}
  a.bm {{ display: inline-block; padding: 8px 14px; background: #e5484d; color: #fff; border-radius: 8px; text-decoration: none; font-weight: 600; }}
  code {{ background: #f2f2f2; padding: 1px 4px; border-radius: 4px; }}
</style>
<h1>page-scrawl</h1>
<p>Drag this to your bookmarks bar:</p>
<p><a class="bm" href="{html.escape(href, quote=True)}">✎ Scrawl</a></p>
<p>Click it on any page to draw on it. After each mark, type (or dictate) what's wrong. Press <b>Done</b>, then tell Claude
"look at my marks". <code>⌥⇧S</code> turns drawing on and off so you can use the page in between.</p>
<p>Sites with a strict Content-Security-Policy may block bookmarklets. Ask Claude to open the overlay there instead.</p>
""")
print(f"wrote {out} ({len(href):,} byte bookmarklet)")
