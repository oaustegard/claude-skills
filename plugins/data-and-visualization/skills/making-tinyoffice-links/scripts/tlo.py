#!/usr/bin/env python3
"""Build, read and pre-flight Tiny Little Office links without a browser or Node.

    tlo.py link APP [FILE|-] [--title T] [--by B] [--view V] [--host H]
    tlo.py read URL                # plain-form link -> its TLO text
    tlo.py lint APP [FILE|-]       # offline subset of the official lint
    tlo.py apps                    # the ten app ids

`link` prints the plain form (`/<app>/#title=..&doc=..`); the site packs it into
`#/v1/<app>/...` on first open. Lint findings go to stderr; exit 1 when any.
Packed links (`#/v1/...`) are not decoded here: open them, or use the official
CLI (`npx tinylittleoffice read`), which owns that codec.
"""
import argparse
import re
import sys
from urllib.parse import parse_qsl, quote_plus, urlsplit

APPS = {
    "write": "Word Processor", "outline": "Outliner", "deck": "Presentation Builder",
    "sheet": "Spreadsheet", "calc": "Calculator", "draw": "Drawing Tool",
    "diagram": "Diagram Maker", "anim": "Animator", "cal": "Calendar", "trip": "Trip Planner",
}
HOST = "https://tinylittleoffice.com"
CHAT_LIMIT = 2000   # some chat apps cut a link past this
SHORT_LIMIT = 12272  # the most a short link holds
FENCE = re.compile(r"^(`{3,})(\w+)?")


def enc(s):
    return quote_plus(s, safe="")


def build(app, doc, title=None, by=None, view=None, host=HOST):
    if app not in APPS:
        raise SystemExit(f"unknown app {app!r}; one of: {', '.join(APPS)}")
    parts = []
    if title:
        parts.append("title=" + enc(title))
    if by:
        parts.append("by=" + enc(by))
    if view:
        parts.append("view=" + enc(view))
    parts.append("doc=" + enc(doc))
    return f"{host.rstrip('/')}/{app}/#" + "&".join(parts)


def read(url):
    """Plain-form link -> (app or None, params dict). None for a packed link."""
    u = urlsplit(url)
    if u.fragment.startswith("/v1/"):
        return None
    app = u.path.strip("/") or None
    return app, dict(parse_qsl(u.fragment, keep_blank_values=True))


def head(doc):
    """The `---` front matter as a dict, and the body after it."""
    lines = doc.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                kv = {}
                for l in lines[1:i]:
                    if ":" in l:
                        k, v = l.split(":", 1)
                        kv[k.strip()] = v.strip()
                return kv, "\n".join(lines[i + 1:])
    return {}, doc


def blocks(body):
    """Split on top-level `---` lines (outside fences): slides, pages, cards."""
    out, cur, fence = [], [], False
    for l in body.split("\n"):
        if FENCE.match(l):
            fence = not fence
        if l.strip() == "---" and not fence:
            out.append("\n".join(cur))
            cur = []
        else:
            cur.append(l)
    out.append("\n".join(cur))
    return out


def names(lines):
    """Things named in a list: text before ` | `, `: ` (for lanes/timeline) is kept whole."""
    got = set()
    for l in lines:
        m = re.match(r"^\s*- (?:\[[ x]\] )?(.+?)(?:\s*\{[^}]*\})?\s*$", l)
        if m:
            got.add(m.group(1).split(" | ")[0].strip())
    return got


def lint(app, doc):
    findings = []
    add = lambda at, kind, msg: findings.append(f"{app} · {at} · {kind}: {msg}")
    kv, body = head(doc)

    if app == "deck":
        for n, slide in enumerate(blocks(body), 1):
            fenced = any(FENCE.match(l) and FENCE.match(l).group(2) for l in slide.split("\n"))
            outside, fence = [], False
            for l in slide.split("\n"):
                if FENCE.match(l):
                    fence = not fence
                    continue
                if not fence:
                    outside.append(l)
            bullets = [l for l in outside if re.match(r"^\s*- ", l)]
            if fenced and bullets:
                add(f"slide {n}", "fence-bullets", f"{len(bullets)} bullet(s) beside a fenced document are not drawn; move them to `> ` notes or their own slide")
            h = next((l for l in outside if l.startswith("## ")), "")
            words = re.sub(r":[\w-]+:|\{[^}]*\}", "", h[3:]).split()
            if len(words) > 9:
                add(f"slide {n}", "title-long", f"headline is {len(words)} words; it shrinks, then cuts after two lines")
            if "{.title}" in h and len(bullets) > 3:
                add(f"slide {n}", "title-list", "a {.title} cover takes a line or two, not a list")
            if len(bullets) > 7:
                add(f"slide {n}", "body-over", f"{len(bullets)} bullets will likely run off the slide; split it")

    if app == "diagram" or (app == "outline"):
        lines = body.split("\n")
        kind = kv.get("kind", "")
        listed = names(lines)
        for l in lines:
            m = re.match(r"^~ (.+?) (?:->|<-|<->|--) (.+?)(?::.*)?$", l)
            if not m:
                continue
            if kind in ("lanes", "timeline", "venn", "seating"):
                add(l, "edge-unused", f"a `{kind}` draws no connections")
            for end in (m.group(1).strip(), m.group(2).strip()):
                if kind != "net" and end not in listed:
                    add(l, "edge-end", f"{end!r} is not a thing in the list (written exactly as before ` | `)")
        if kind == "net":
            for l in lines:
                if re.match(r"^\s*- [^~].*: ", l):
                    add(l.strip(), "net-colon", "in a net the whole line is the name; put the description in a label")
        if kind in ("venn", "seating"):
            for l in lines:
                if re.search(r"\d,\d{3}", l):
                    add(l.strip(), "comma-number", "a comma inside a number splits it into two things; write 2000")
        for l in lines:
            m = re.match(r"^\s*- (?:\[[ x]\] )?([^|:{]+)", l)
            if m and kind and len(m.group(1).split()) > 6:
                add(l.strip(), "label-long", "a thing is a short name (two to four words); put the rest in a child or label")

    if re.search(r"tinylittleoffice\.com/\w+/#", body):
        add("words", "doc-link", "a link to another TLO document; put it inside as a ```<app> fence instead")
    return findings


def source(path):
    if path in (None, "-"):
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    lk = sub.add_parser("link")
    lk.add_argument("app")
    lk.add_argument("file", nargs="?")
    lk.add_argument("--title")
    lk.add_argument("--by")
    lk.add_argument("--view")
    lk.add_argument("--host", default=HOST)
    lk.add_argument("--no-lint", action="store_true")
    rd = sub.add_parser("read")
    rd.add_argument("url")
    li = sub.add_parser("lint")
    li.add_argument("app")
    li.add_argument("file", nargs="?")
    sub.add_parser("apps")
    a = p.parse_args()

    if a.cmd == "apps":
        for k, v in APPS.items():
            print(f"{k:8} {v}")
        return 0
    if a.cmd == "read":
        r = read(a.url)
        if r is None:
            print("packed link (#/v1/...): open it, or `npx tinylittleoffice read <link>`", file=sys.stderr)
            return 2
        app, q = r
        doc = q.get("doc", q.get("md", ""))
        meta = {k: v for k, v in q.items() if k not in ("doc", "md")}
        if app or meta:
            print(f"# app={app or '(from head)'} " + " ".join(f"{k}={v}" for k, v in meta.items()), file=sys.stderr)
        sys.stdout.write(doc if doc.endswith("\n") else doc + "\n")
        return 0
    doc = source(a.file).rstrip("\n")
    found = lint(a.app, doc)
    if a.cmd == "lint":
        for f in found:
            print(f, file=sys.stderr)
        return 1 if found else 0
    url = build(a.app, doc, a.title, a.by, a.view, a.host)
    print(url)
    if not a.no_lint:
        for f in found:
            print(f, file=sys.stderr)
    n = len(url)
    if n > SHORT_LIMIT:
        print(f"length: {n} chars, over the {SHORT_LIMIT} a short link holds; cut the document", file=sys.stderr)
    elif n > CHAT_LIMIT:
        print(f"length: {n} chars; some chat apps cut past {CHAT_LIMIT}: deliver it in a code block, or as a short link", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
