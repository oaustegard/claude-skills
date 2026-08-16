#!/usr/bin/env python3
"""atproto — AppView-independent reads of the atmosphere.

Every read declares WHAT it needs; the resolver picks a surviving SOURCE.

    PDS            authoritative repo records  (never went down 2026-08-16)
    Constellation  backlink index: who liked/replied/quoted/reposted X
    plc.directory  handle <-> DID <-> PDS location
    AppView        convenience only; search & feedgens have no substitute

State is a /tmp SQLite scratch, session-scoped by design. Nothing persists;
Constellation is the persistent index and someone else operates it.

Output defaults to a compact digest. --json emits raw structures, for when the
caller will actually transform them. Keeping payloads out of the transcript is
the entire point: wall-clock cost and token cost are decoupled.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

PLC = "https://plc.directory"
CONSTELLATION = "https://constellation.microcosm.blue"
APPVIEW = "https://public.api.bsky.app/xrpc"
ENTRYWAY = "https://bsky.social"
DB = os.environ.get("ATPROTO_CACHE", "/tmp/atproto-scratch.db")
UA = "atprotoing/0.1"

# TID: 13 chars, base32-sortable. Top 53 bits are microseconds since epoch,
# low 10 are a clock id. Client-generated, so times are approximate and in
# principle spoofable -- good enough for ordering, not for attestation.
TID_CHARS = "234567abcdefghijklmnopqrstuvwxyz"

# Where interaction records point at their target. Quotes appear under two
# different paths depending on whether the embed is bare or a recordWithMedia.
LINK_PATHS = [
    ("app.bsky.feed.like", ".subject.uri", "like"),
    ("app.bsky.feed.repost", ".subject.uri", "repost"),
    ("app.bsky.feed.post", ".reply.parent.uri", "reply"),
    ("app.bsky.feed.post", ".embed.record.uri", "quote"),
    ("app.bsky.feed.post", ".embed.record.record.uri", "quote"),
]


# ── transport ──────────────────────────────────────────────────────────

class Unavailable(Exception):
    """A source is unreachable. Callers degrade explicitly rather than fail."""


def http(url, params=None, body=None, headers=None, timeout=25, tries=3):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    hdrs = {"User-Agent": UA, **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read()[:200].decode("utf8", "replace")
            if e.code == 403 and "not in allowlist" in detail:
                raise Unavailable(f"egress blocked: {urllib.parse.urlsplit(url).netloc}")
            if 400 <= e.code < 500 and e.code != 429:
                raise Unavailable(f"HTTP {e.code}: {detail}")
            last = e
        except Exception as e:  # timeout, DNS, reset
            last = e
        if attempt < tries - 1:
            import time
            time.sleep(1.5 * (attempt + 1))
    raise Unavailable(f"{type(last).__name__}: {str(last)[:120]}")


def parallel(fn, items, workers=16):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))


# ── scratch cache ──────────────────────────────────────────────────────

def db():
    c = sqlite3.connect(DB)
    c.executescript(
        "CREATE TABLE IF NOT EXISTS ident("
        " did TEXT PRIMARY KEY, handle TEXT, pds TEXT);"
        "CREATE TABLE IF NOT EXISTS link("
        " did TEXT, rkey TEXT, kind TEXT, target TEXT, at TEXT,"
        " PRIMARY KEY (did, rkey, kind, target));"
    )
    return c


# ── identity ───────────────────────────────────────────────────────────

def tid_time(rkey):
    try:
        v = 0
        for ch in rkey[:13]:
            v = v * 32 + TID_CHARS.index(ch)
        return dt.datetime.fromtimestamp((v >> 10) / 1e6, dt.UTC)
    except (ValueError, OSError, OverflowError):
        return None


def resolve(actor, conn=None):
    """handle|did -> {did, handle, pds}. DNS-free: PLC is authoritative."""
    conn = conn or db()
    row = conn.execute(
        "SELECT did,handle,pds FROM ident WHERE did=? OR handle=?", (actor, actor)
    ).fetchone()
    if row and row[2]:
        return {"did": row[0], "handle": row[1], "pds": row[2]}

    did = actor
    if not actor.startswith("did:"):
        # Entryway resolution needs no AppView and covers hosted + custom handles.
        did = http(f"{ENTRYWAY}/xrpc/com.atproto.identity.resolveHandle",
                   {"handle": actor})["did"]
    doc = http(f"{PLC}/{did}")
    pds = next((s["serviceEndpoint"] for s in doc.get("service", [])
                if s.get("type") == "AtprotoPersonalDataServer"), None)
    aka = [a[5:] for a in doc.get("alsoKnownAs", []) if a.startswith("at://")]
    out = {"did": did, "handle": aka[0] if aka else did, "pds": pds}
    conn.execute("INSERT OR REPLACE INTO ident VALUES (?,?,?)",
                 (out["did"], out["handle"], out["pds"]))
    conn.commit()
    return out


def resolve_many(dids, conn=None):
    conn = conn or db()
    known = dict(conn.execute(
        "SELECT did,handle FROM ident WHERE handle IS NOT NULL").fetchall())
    todo = [d for d in dids if d not in known]

    def one(d):
        try:
            return d, resolve(d, db())["handle"]
        except Unavailable:
            return d, d

    for d, h in parallel(one, todo, workers=20):
        known[d] = h
    return known


# ── repo reads (PDS: authoritative, survived the outage) ───────────────

def records(repo, collection, pds=None, limit=None, conn=None):
    """All records of a collection, paged. Reads the repo itself, not an index."""
    ident = resolve(repo, conn)
    pds = pds or ident["pds"]
    if not pds:
        raise Unavailable(f"no PDS in DID document for {repo}")
    out, cursor = [], None
    while True:
        p = {"repo": ident["did"], "collection": collection, "limit": 100}
        if cursor:
            p["cursor"] = cursor
        page = http(f"{pds}/xrpc/com.atproto.repo.listRecords", p)
        out += page["records"]
        cursor = page.get("cursor")
        if not cursor or not page["records"] or (limit and len(out) >= limit):
            break
    return out[:limit] if limit else out


# ── backlinks (Constellation: the borrowed index) ──────────────────────

def links_all(target):
    return http(f"{CONSTELLATION}/links/all", {"target": target}).get("links", {})


def links(target, collection, path):
    out, cursor = [], None
    while True:
        p = {"target": target, "collection": collection, "path": path}
        if cursor:
            p["cursor"] = cursor
        r = http(f"{CONSTELLATION}/links", p)
        out += r.get("linking_records", [])
        cursor = r.get("cursor")
        if not cursor:
            return out


def interactions(actor, since_hours=8, scan=100, conn=None):
    """Every like/reply/repost/quote landing on actor's recent posts.

    Two-phase on purpose: links/all is one cheap call per post that reports
    which paths are non-empty, so the expensive per-path enumeration only runs
    where something exists.
    """
    conn = conn or db()
    me = resolve(actor, conn)
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=since_hours)
    posts = records(me["did"], "app.bsky.feed.post", limit=scan, conn=conn)
    by_uri = {p["uri"]: p["value"].get("text", "") for p in posts}

    def probe(uri):
        try:
            present = links_all(uri)
        except Unavailable:
            return []
        hits = []
        for coll, path, kind in LINK_PATHS:
            node = present.get(coll, {}).get(path)
            if not node or not node.get("records"):
                continue
            try:
                found = links(uri, coll, path)
            except Unavailable:
                continue
            for lr in found:
                at = tid_time(lr["rkey"])
                if at and at >= cutoff:
                    hits.append({"kind": kind, "did": lr["did"], "rkey": lr["rkey"],
                                 "at": at, "target": uri})
        return hits

    rows = [h for group in parallel(probe, list(by_uri), workers=8) for h in group]
    for h in rows:  # dedupe: quotes match two paths
        conn.execute("INSERT OR REPLACE INTO link VALUES (?,?,?,?,?)",
                     (h["did"], h["rkey"], h["kind"], h["target"], h["at"].isoformat()))
    conn.commit()
    uniq = {(h["did"], h["rkey"], h["kind"], h["target"]): h for h in rows}
    rows = sorted(uniq.values(), key=lambda h: h["at"])
    handles = resolve_many({h["did"] for h in rows}, conn)
    for h in rows:
        h["handle"] = handles.get(h["did"], h["did"])
        h["text"] = by_uri.get(h["target"], "")
    return rows


def thread(uri, conn=None):
    """Reconstruct replies without getPostThread: Constellation finds the
    reply records, each author's own PDS serves the content."""
    conn = conn or db()
    kids = links(uri, "app.bsky.feed.post", ".reply.parent.uri")

    def fetch(lr):
        try:
            ident = resolve(lr["did"], db())
            r = http(f"{ident['pds']}/xrpc/com.atproto.repo.getRecord",
                     {"repo": lr["did"], "collection": "app.bsky.feed.post",
                      "rkey": lr["rkey"]})
            return {"handle": ident["handle"], "rkey": lr["rkey"],
                    "at": tid_time(lr["rkey"]), "text": r["value"].get("text", ""),
                    "uri": r["uri"]}
        except Unavailable:
            return None

    got = [x for x in parallel(fetch, kids, workers=12) if x]
    return sorted(got, key=lambda x: x["at"] or dt.datetime.min.replace(tzinfo=dt.UTC))


# ── health ─────────────────────────────────────────────────────────────

def status(actor=None):
    """Layer-by-layer probe. Distinguishes 'atproto is down' from 'Bluesky
    PLC's AppView is down' -- they are not the same outage and the tool should
    say which one is happening."""
    import time
    checks = [
        ("PDS entryway", lambda: http(f"{ENTRYWAY}/xrpc/_health")),
        ("PLC directory", lambda: http(f"{PLC}/did:plc:z72i7hdynmk6r22z27h6tvur")),
        ("Constellation", lambda: http(f"{CONSTELLATION}/links/count", {
            "target": "did:plc:z72i7hdynmk6r22z27h6tvur",
            "collection": "app.bsky.graph.follow", "path": ".subject"})),
        ("AppView", lambda: http(f"{APPVIEW}/app.bsky.actor.getProfile",
                                 {"actor": "bsky.app"}, timeout=12, tries=1)),
    ]
    if actor:
        ident = resolve(actor)
        checks.insert(1, (f"PDS {urllib.parse.urlsplit(ident['pds']).netloc}",
                          lambda: http(f"{ident['pds']}/xrpc/com.atproto.repo.describeRepo",
                                       {"repo": ident["did"]})))
    out = []
    for name, fn in checks:
        t0 = time.time()
        try:
            fn()
            out.append({"layer": name, "ok": True, "ms": int((time.time() - t0) * 1000)})
        except Unavailable as e:
            out.append({"layer": name, "ok": False, "ms": int((time.time() - t0) * 1000),
                        "err": str(e)[:80]})
    return out


# ── digests ────────────────────────────────────────────────────────────

def fmt_interactions(rows, hours):
    if not rows:
        return f"No interactions in the last {hours}h."
    kinds = Counter(r["kind"] for r in rows)
    plural = {"reply": "replies", "like": "likes",
              "repost": "reposts", "quote": "quotes"}
    head = (f"{len(rows)} interactions / {hours}h — "
            + " · ".join(f"{n} {plural[k] if n > 1 else k}"
                         for k, n in kinds.most_common()))
    groups = defaultdict(list)
    for r in rows:
        groups[r["target"]].append(r)
    order = sorted(groups, key=lambda t: max(x["at"] for x in groups[t]), reverse=True)
    lines = [head, ""]
    for t in order:
        g = groups[t]
        snippet = re.sub(r"\s+", " ", g[0]["text"])[:64]
        lines.append(f"— {snippet!r}  (/{t.rsplit('/', 1)[1]})")
        for r in sorted(g, key=lambda x: x["at"]):
            lines.append(f"    {r['at']:%H:%M}Z  {r['kind']:<6} {r['handle']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def fmt_status(rows):
    lines = []
    for r in rows:
        mark = "ok  " if r["ok"] else "DOWN"
        lines.append(f"{mark} {r['layer']:<28} {r['ms']:>5}ms"
                     + ("" if r["ok"] else f"  {r.get('err', '')}"))
    down = [r["layer"] for r in rows if not r["ok"]]
    if down and all("AppView" in d for d in down):
        lines.append("\nAppView-only failure: repo reads and Constellation still work.")
    elif down:
        lines.append(f"\nDegraded: {', '.join(down)}")
    return "\n".join(lines)


def fmt_thread(rows):
    if not rows:
        return "No replies indexed."
    return "\n".join(
        f"{r['at']:%m-%d %H:%M}Z  {r['handle']:<28} {re.sub(chr(10), ' ', r['text'])[:80]}"
        for r in rows)


def fmt_posts(recs):
    lines = []
    for r in recs:
        v = r["value"]
        lines.append(f"{v.get('createdAt', '')[:16]}  /{r['uri'].rsplit('/', 1)[1]}  "
                     + re.sub(r"\s+", " ", v.get("text", ""))[:80])
    return "\n".join(lines)


# ── cli ────────────────────────────────────────────────────────────────

def main(argv=None):
    # --json is accepted on either side of the subcommand; requiring it before
    # the verb is a papercut nobody remembers.
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS: without it the subparser's default False overwrites a --json
    # given before the verb.
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="raw structures, not a digest")
    ap = argparse.ArgumentParser(prog="atproto", parents=[common],
                                 description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=(
        lambda **kw: argparse.ArgumentParser(parents=[common], **kw)))

    s = sub.add_parser("status", help="layer-by-layer health probe")
    s.add_argument("--actor", help="also probe this actor's own PDS")

    s = sub.add_parser("resolve", help="handle/DID -> did, handle, PDS")
    s.add_argument("actor")

    s = sub.add_parser("interactions", help="likes/replies/reposts/quotes on recent posts")
    s.add_argument("actor")
    s.add_argument("--hours", type=int, default=8)
    s.add_argument("--scan", type=int, default=100, help="how many recent posts to check")

    s = sub.add_parser("posts", help="an actor's posts, read from their PDS")
    s.add_argument("actor")
    s.add_argument("--limit", type=int, default=25)

    s = sub.add_parser("thread", help="replies to a post, via Constellation + PDSes")
    s.add_argument("uri")

    s = sub.add_parser("feed", help="following timeline, rebuilt from PDSes")
    s.add_argument("actor", nargs="?", default="austegard.com")
    s.add_argument("--hours", type=float, default=3.0)
    s.add_argument("--html", metavar="PATH", help="write the threaded reader here")
    s.add_argument("--no-reposts", action="store_true")

    s = sub.add_parser("records", help="any collection from any repo")
    s.add_argument("actor")
    s.add_argument("collection")
    s.add_argument("--limit", type=int, default=100)

    a = ap.parse_args(argv)
    as_json = getattr(a, "json", False)
    conn = db()

    try:
        if a.cmd == "status":
            r = status(a.actor)
            print(json.dumps(r, indent=2) if as_json else fmt_status(r))
        elif a.cmd == "resolve":
            print(json.dumps(resolve(a.actor, conn), indent=2))
        elif a.cmd == "interactions":
            r = interactions(a.actor, a.hours, a.scan, conn)
            if as_json:
                print(json.dumps([{**x, "at": x["at"].isoformat()} for x in r], indent=2))
            else:
                print(fmt_interactions(r, a.hours))
        elif a.cmd == "posts":
            r = records(a.actor, "app.bsky.feed.post", limit=a.limit, conn=conn)
            print(json.dumps(r, indent=2) if as_json else fmt_posts(r))
        elif a.cmd == "thread":
            r = thread(a.uri, conn)
            if as_json:
                print(json.dumps([{**x, "at": x["at"].isoformat() if x["at"] else None}
                                  for x in r], indent=2))
            else:
                print(fmt_thread(r))
        elif a.cmd == "feed":
            from feed import build, fmt, to_html
            d = build(a.actor, a.hours, want_reposts=not a.no_reposts)
            if a.html:
                print(to_html(d, a.html))
            if as_json:
                print(json.dumps(d, indent=1))
            elif not a.html:
                print(fmt(d))
        elif a.cmd == "records":
            r = records(a.actor, a.collection, limit=a.limit, conn=conn)
            print(json.dumps(r, indent=2) if as_json else fmt_posts(r))
    except Unavailable as e:
        print(f"unavailable: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
