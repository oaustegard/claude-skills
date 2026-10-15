#!/usr/bin/env python3
"""Build, read and pre-flight Tiny Little Office links without a browser or Node.

    tlo.py link APP [FILE|-] [--title T] [--by B] [--view V] [--plain] [--host H]
    tlo.py read URL                # packed or plain link -> its TLO text
    tlo.py repair URL              # a chat-mangled packed link -> a clean one
    tlo.py lint APP [FILE|-]       # offline subset of the official lint
    tlo.py apps                    # the ten app ids

`link` prints the packed form the site itself shares (`#/v1/<app>/<flag><payload>`):
the TLO deflated against TLO's frozen dictionary (`y`), deflated (`z`) or raw
(`r`), whichever is shortest, in base64url with `-` for 62 and a `+` every 300
characters. The site writes `~` for 62 and reads `-` too; `~` gets percent-encoded
(even twice, `%257E`) by some chat clients (Webex), and the site does not
percent-decode, so `-` is the default here; `--tilde` matches the site's own. `--plain` prints `/<app>/#title=..&doc=..` instead. Lint findings go
to stderr; `lint` exits 1 when any. The dictionary (scripts/tlo_dictionary.txt)
is copied from aboard-io/tinylittleoffice src/kit/core/codec.ts (MIT).
"""
import argparse
import re
import sys
import zlib
from pathlib import Path
from urllib.parse import parse_qsl, quote_plus, unquote, urlsplit

APPS = {
    "write": "Word Processor", "outline": "Outliner", "deck": "Presentation Builder",
    "sheet": "Spreadsheet", "calc": "Calculator", "draw": "Drawing Tool",
    "diagram": "Diagram Maker", "anim": "Animator", "cal": "Calendar", "trip": "Trip Planner",
}
HOST = "https://tinylittleoffice.com"
CHAT_LIMIT = 2000   # some chat apps cut a link past this
SHORT_LIMIT = 12272  # the most a short link holds
FENCE = re.compile(r"^(`{3,})(\w+)?")
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
B64_REV = {c: i for i, c in enumerate(B64)} | {"~": 62}
BREAK_EVERY = 300
DICTIONARY = (Path(__file__).with_name("tlo_dictionary.txt")).read_bytes()


def b64e(data: bytes, tilde: bool = False) -> str:
    out = []
    for i in range(0, len(data), 3):
        chunk = data[i:i + 3]
        n = int.from_bytes(chunk.ljust(3, b"\0"), "big")
        out.append("".join(B64[(n >> s) & 63] for s in (18, 12, 6, 0))[:len(chunk) + 1])
    text = "".join(out)
    return text.replace("-", "~") if tilde else text


def b64d(s: str) -> bytes:
    bits = n = 0
    out = bytearray()
    for c in s:
        n = (n << 6) | B64_REV[c]
        bits += 6
        if bits >= 8:
            bits -= 8
            out.append((n >> bits) & 255)
    return bytes(out)


def deflate(raw: bytes, zdict: bytes | None = None) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -15, 9, **({"zdict": zdict} if zdict else {}))
    return c.compress(raw) + c.flush()


def breaks(bare: str) -> str:
    return "+".join(bare[i:i + BREAK_EVERY] for i in range(0, len(bare), BREAK_EVERY))


def pack(doc: str, tilde: bool = False) -> str:
    """TLO text -> flag + base64url payload, the shortest of y / z / r, with breaks."""
    raw = doc.encode("utf-8")
    flag, data = min((("r", raw), ("z", deflate(raw)), ("y", deflate(raw, DICTIONARY))), key=lambda x: len(x[1]))
    return breaks(flag + b64e(data, tilde))


def clean(payload: str) -> str:
    """Undo what chat clients do to a payload: percent-encoding (once or twice), a
    trailing quote or bracket swallowed into the link, the `+` breaks."""
    p = payload
    for _ in range(3):
        if "%" not in p:
            break
        p = unquote(p)
    p = p.split("?")[0].replace("+", "")
    return re.sub(r"[^A-Za-z0-9_~-].*$", "", p, flags=re.S)


def unpack(payload: str) -> str:
    p = clean(payload)
    flag, data = p[0], b64d(p[1:])
    if flag == "r":
        return data.decode("utf-8")
    if flag not in "yz":
        raise ValueError(f"unsupported payload flag {flag!r} (E is a sealed, password link)")
    d = zlib.decompressobj(-15, zdict=DICTIONARY) if flag == "y" else zlib.decompressobj(-15)
    return (d.decompress(data) + d.flush()).decode("utf-8")


def with_head(doc: str, **fields: str | None) -> str:
    """Put title/by into the document's head, where a packed link carries them."""
    fields = {k: v for k, v in fields.items() if v}
    if not fields:
        return doc
    kv, body = head(doc)
    lines = doc.split("\n")
    if kv or (lines and lines[0].strip() == "---"):
        end = lines.index("---", 1)
        have = {l.split(":", 1)[0].strip() for l in lines[1:end]}
        add = [f"{k}: {v}" for k, v in fields.items() if k not in have]
        return "\n".join(lines[:1] + add + lines[1:])
    return "---\n" + "".join(f"{k}: {v}\n" for k, v in fields.items()) + "---\n" + doc


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


def build_packed(app, doc, title=None, by=None, view=None, host=HOST, tilde=False):
    if app not in APPS:
        raise SystemExit(f"unknown app {app!r}; one of: {', '.join(APPS)}")
    path = f"{app}.{view}" if view and view not in ("show",) else app
    tail = "?show" if view == "show" else ""
    return f"{host.rstrip('/')}/{app}/#/v1/{path}/" + pack(with_head(doc, title=title, by=by), tilde) + tail


def repair(url: str, tilde: bool = False) -> str:
    """A packed link mangled in transit -> the same document's clean link (same bytes)."""
    u = urlsplit(url.strip().strip("<>\"'‘’“”"))
    frag = unquote(u.fragment) if u.fragment.startswith("%2F") else u.fragment
    _, _, where, payload = frag.split("/", 3)
    query = re.search(r"\?(show|d)\b", unquote(unquote(payload)))
    p = clean(payload)
    unpack(p)  # raises if the bytes do not decode
    bare = p.replace("~", "-") if not tilde else p.replace("-", "~")
    return f"{u.scheme}://{u.netloc}{u.path}#/v1/{where}/" + breaks(bare) + (f"?{query.group(1)}" if query else "")


def read(url):
    """Link -> (app or None, params dict); a packed link's text comes back as params['doc']."""
    u = urlsplit(url)
    if u.fragment.startswith("/v1/"):
        _, _, where, payload = u.fragment.split("/", 3)
        return where.split(".")[0], {"doc": unpack(payload.split("?")[0])}
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
    lk.add_argument("--plain", action="store_true", help="the readable #doc= form instead of the packed one")
    lk.add_argument("--tilde", action="store_true", help="write ~ for 62, as the site does (breaks in Webex)")
    lk.add_argument("--no-lint", action="store_true")
    rd = sub.add_parser("read")
    rd.add_argument("url")
    rp = sub.add_parser("repair")
    rp.add_argument("url")
    rp.add_argument("--tilde", action="store_true")
    li = sub.add_parser("lint")
    li.add_argument("app")
    li.add_argument("file", nargs="?")
    sub.add_parser("apps")
    a = p.parse_args()

    if a.cmd == "apps":
        for k, v in APPS.items():
            print(f"{k:8} {v}")
        return 0
    if a.cmd == "repair":
        try:
            print(repair(a.url, a.tilde))
        except (ValueError, KeyError, zlib.error) as e:
            print(f"cannot repair this link: {e}", file=sys.stderr)
            return 2
        return 0
    if a.cmd == "read":
        try:
            app, q = read(a.url)
        except (ValueError, KeyError, zlib.error) as e:
            print(f"cannot read this link: {e}", file=sys.stderr)
            return 2
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
    if a.plain:
        url = build(a.app, doc, a.title, a.by, a.view, a.host)
    else:
        url = build_packed(a.app, doc, a.title, a.by, a.view, a.host, a.tilde)
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
