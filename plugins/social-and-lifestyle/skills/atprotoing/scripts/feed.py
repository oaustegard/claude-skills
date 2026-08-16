#!/usr/bin/env python3
"""Following-feed reconstruction, AppView-free.

There is no AppView-free `getTimeline`, so the feed is rebuilt from primitives:

    own PDS  -> app.bsky.graph.follow records
    PLC      -> each followee's DID document -> PDS host
    each PDS -> app.bsky.feed.post + app.bsky.feed.repost, newest page
    each PDS -> app.bsky.actor.profile (display name, avatar blob)

Records come back RAW, not hydrated: facets are byte ranges, embeds are blob
refs, quoted posts are bare URIs. Everything the AppView would have inlined is
resolved here instead -- byte offsets to character offsets, blob CIDs to
cdn.bsky.app URLs, quote/parent URIs to fetched records -- so the reader gets
the same shape `getPostThread` would have handed it.

Output is threaded, not a flat reverse-chron list: posts are clustered by reply
root, ancestors outside the window are fetched one hop for context, and clusters
are ordered by most recent activity.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading

try:
    from . import atproto as A
except ImportError:  # run as a script, not a package
    import atproto as A

CDN = "https://cdn.bsky.app/img"
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feed_reader.html")
_lock = threading.Lock()


# ── hydration helpers ──────────────────────────────────────────────────

def blob_cid(blob):
    """Blob ref -> CID string. listRecords renders refs as {'$link': cid}."""
    if not isinstance(blob, dict):
        return None
    ref = blob.get("ref")
    if isinstance(ref, dict):
        return ref.get("$link")
    return ref if isinstance(ref, str) else None


def img_url(did, blob, kind="feed_thumbnail"):
    cid = blob_cid(blob)
    return f"{CDN}/{kind}/plain/{did}/{cid}@jpeg" if cid else None


def char_facets(text, facets):
    """Byte ranges -> character ranges. The wire format indexes UTF-8 bytes;
    every renderer indexes characters, and the two diverge on any non-ASCII."""
    if not facets:
        return []
    raw = text.encode("utf8")
    out = []
    for f in facets:
        idx = f.get("index") or {}
        uri = next((ft.get("uri") for ft in f.get("features", [])
                    if ft.get("$type") == "app.bsky.richtext.facet#link"), None)
        tag = next((ft.get("tag") for ft in f.get("features", [])
                    if ft.get("$type") == "app.bsky.richtext.facet#tag"), None)
        did = next((ft.get("did") for ft in f.get("features", [])
                    if ft.get("$type") == "app.bsky.richtext.facet#mention"), None)
        if not (uri or tag or did):
            continue
        try:
            s = len(raw[:idx["byteStart"]].decode("utf8", "ignore"))
            e = len(raw[:idx["byteEnd"]].decode("utf8", "ignore"))
        except (KeyError, TypeError):
            continue
        if tag:
            uri = f"https://bsky.app/hashtag/{tag}"
        elif did:
            uri = f"https://bsky.app/profile/{did}"
        out.append({"s": s, "e": e, "uri": uri})
    return sorted(out, key=lambda f: f["s"])


def embed_of(did, v):
    """Raw embed record -> renderable structure. Quote URIs are returned for
    the caller to fetch; blobs become CDN URLs."""
    e = v.get("embed") or {}
    t = e.get("$type", "")
    media = e.get("media") if "recordWithMedia" in t else e
    mt = (media or {}).get("$type", "")
    out, quote = None, None

    if "images" in mt:
        imgs = []
        for im in media.get("images", []):
            ar = im.get("aspectRatio") or {}
            imgs.append({
                "thumb": img_url(did, im.get("image")),
                "full": img_url(did, im.get("image"), "feed_fullsize"),
                "alt": im.get("alt", ""),
                "ar": f'{ar.get("width", 16)}/{ar.get("height", 9)}',
            })
        imgs = [i for i in imgs if i["thumb"]]
        if imgs:
            out = {"kind": "images", "images": imgs}
    elif "video" in mt:
        ar = media.get("aspectRatio") or {}
        out = {"kind": "video",
               "thumb": img_url(did, media.get("video"), "feed_thumbnail"),
               "ar": f'{ar.get("width", 16)}/{ar.get("height", 9)}'}
    elif "external" in mt:
        x = media.get("external") or {}
        out = {"kind": "link", "uri": x.get("uri", ""), "title": x.get("title", ""),
               "desc": x.get("description", ""),
               "thumb": img_url(did, x.get("thumb"))}

    if "record" in t:
        rec = e.get("record") or {}
        quote = rec.get("uri") or (rec.get("record") or {}).get("uri")
    return out, quote


def parse_uri(uri):
    try:
        did, coll, rkey = uri.split("at://", 1)[1].split("/")
        return did, coll, rkey
    except (IndexError, ValueError):
        return None, None, None


# ── identity / profile ─────────────────────────────────────────────────

def profiles(dids, cache):
    """displayName + avatar per DID, straight from each repo's profile record."""
    todo = [d for d in dids if d not in cache]

    def one(did):
        try:
            i = A.resolve(did, A.db())
            r = A.http(f"{i['pds']}/xrpc/com.atproto.repo.getRecord",
                       {"repo": did, "collection": "app.bsky.actor.profile",
                        "rkey": "self"}, timeout=15, tries=2)
            v = r.get("value", {})
            p = {"handle": i["handle"], "name": v.get("displayName") or i["handle"],
                 "avatar": img_url(did, v.get("avatar"), "avatar_thumbnail")}
        except Exception:
            try:
                h = A.resolve(did, A.db())["handle"]
            except Exception:
                h = did
            p = {"handle": h, "name": h, "avatar": None}
        with _lock:
            cache[did] = p

    A.parallel(one, todo, workers=24)
    return cache


# ── the fan-out ────────────────────────────────────────────────────────

def collect(actor, hours=3.0, page=30, want_reposts=True):
    now = dt.datetime.now(dt.UTC)
    cutoff = now - dt.timedelta(hours=hours)
    ceiling = now + dt.timedelta(minutes=10)  # clock skew on client-set times
    conn = A.db()
    me = A.resolve(actor, conn)

    follows = A.records(actor, "app.bsky.graph.follow", conn=conn)
    dids = sorted({r["value"]["subject"] for r in follows})

    ident, fail = {}, {}

    def res(did):
        try:
            i = A.resolve(did, A.db())
            if not i.get("pds"):
                raise A.Unavailable("no PDS in DID document")
            with _lock:
                ident[did] = i
        except Exception as e:
            with _lock:
                fail[did] = str(e)[:90]

    A.parallel(res, dids, workers=24)

    def in_window(v):
        try:
            t = dt.datetime.fromisoformat(
                (v.get("createdAt") or "").replace("Z", "+00:00"))
        except ValueError:
            return None
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.UTC)
        return t if cutoff <= t <= ceiling else None

    posts, reposts = [], []

    def pull(did):
        i = ident[did]
        for coll, sink in (("app.bsky.feed.post", posts),
                           ("app.bsky.feed.repost", reposts)):
            if coll.endswith("repost") and not want_reposts:
                continue
            try:
                pg = A.http(f"{i['pds']}/xrpc/com.atproto.repo.listRecords",
                            {"repo": did, "collection": coll, "limit": page},
                            timeout=20, tries=2)
            except Exception as e:
                with _lock:
                    fail.setdefault(did, str(e)[:90])
                continue
            for r in pg.get("records", []):
                t = in_window(r.get("value", {}))
                if t:
                    with _lock:
                        sink.append((did, r, t))

    A.parallel(pull, list(ident), workers=24)
    return {"me": me, "now": now, "cutoff": cutoff, "hours": hours,
            "follows": len(dids), "resolved": len(ident), "fail": fail,
            "posts": posts, "reposts": reposts, "conn": conn}


def fetch_post(uri):
    did, coll, rkey = parse_uri(uri)
    if not did:
        return None
    i = A.resolve(did, A.db())
    r = A.http(f"{i['pds']}/xrpc/com.atproto.repo.getRecord",
               {"repo": did, "collection": coll, "rkey": rkey}, timeout=15, tries=2)
    return did, r.get("value", {}), rkey


def shape(did, v, rkey, at=None, ctx=False):
    emb, quote = embed_of(did, v)
    reply = v.get("reply") or {}
    return {
        "uri": f"at://{did}/app.bsky.feed.post/{rkey}",
        "did": did, "rkey": rkey,
        "at": (at.isoformat() if at else v.get("createdAt", "")),
        "text": v.get("text", ""),
        "facets": char_facets(v.get("text", ""), v.get("facets")),
        "parent": ((reply.get("parent") or {}).get("uri")),
        "root": ((reply.get("root") or {}).get("uri")),
        "embed": emb, "quoteUri": quote, "quote": None,
        "repost": None, "ctx": ctx,
    }


def build(actor="austegard.com", hours=3.0, want_reposts=True):
    raw = collect(actor, hours, want_reposts=want_reposts)
    items, seen = {}, set()

    for did, r, t in raw["posts"]:
        p = shape(did, r["value"], r["uri"].rsplit("/", 1)[1], t)
        items[p["uri"]] = p
        seen.add(p["uri"])

    # Reposts: the event is the repost, the content is someone else's record.
    rp_targets = {}
    for did, r, t in raw["reposts"]:
        subj = ((r["value"].get("subject") or {}).get("uri"))
        if subj:
            rp_targets.setdefault(subj, []).append((did, t))

    fetched = {}

    def grab(uri):
        try:
            got = fetch_post(uri)
            if got:
                with _lock:
                    fetched[uri] = got
        except Exception:
            pass

    A.parallel(grab, [u for u in rp_targets if u not in items], workers=24)

    for uri, actors in rp_targets.items():
        for by_did, t in actors:
            if uri in items and items[uri].get("repost") is None and uri not in fetched:
                # already in-window from the author; annotate rather than duplicate
                items[uri]["repost"] = {"did": by_did, "at": t.isoformat()}
                continue
            got = fetched.get(uri)
            if not got:
                continue
            d, v, rk = got
            p = shape(d, v, rk)
            p["repost"] = {"did": by_did, "at": t.isoformat()}
            p["at_event"] = t.isoformat()
            items[uri + "#rp:" + by_did] = p

    # One hop of missing ancestors, so replies are not orphaned, plus quotes.
    need = set()
    for p in list(items.values()):
        if p["parent"] and p["parent"] not in items:
            need.add(p["parent"])
        if p["quoteUri"] and p["quoteUri"] not in items:
            need.add(p["quoteUri"])
    fetched2 = {}

    def grab2(uri):
        try:
            got = fetch_post(uri)
            if got:
                with _lock:
                    fetched2[uri] = got
        except Exception:
            pass

    A.parallel(grab2, sorted(need), workers=24)

    ctx = {}
    for uri, (d, v, rk) in fetched2.items():
        ctx[uri] = shape(d, v, rk, ctx=True)

    for p in items.values():
        if p["quoteUri"]:
            q = items.get(p["quoteUri"]) or ctx.get(p["quoteUri"])
            if q:
                p["quote"] = {k: q[k] for k in
                              ("uri", "did", "rkey", "at", "text", "facets", "embed")}

    for uri, p in ctx.items():
        if uri not in items and any(x["parent"] == uri for x in items.values()):
            items[uri] = p

    prof = profiles({p["did"] for p in items.values()}
                    | {p["repost"]["did"] for p in items.values() if p["repost"]}
                    | {(p["quote"] or {}).get("did") for p in items.values() if p["quote"]}
                    - {None}, {})

    out = []
    for p in items.values():
        p.update(prof.get(p["did"], {}))
        if p["repost"]:
            p["repost"].update(prof.get(p["repost"]["did"], {}))
        if p["quote"]:
            p["quote"].update(prof.get(p["quote"]["did"], {}))
        p.pop("quoteUri", None)
        out.append(p)
    out.sort(key=lambda p: p.get("at_event") or p["at"], reverse=True)

    fails = list(raw["fail"].values())
    blocked = sorted({f.split(": ", 1)[1] for f in fails if f.startswith("egress blocked")})
    gone = sum(1 for f in fails if "Could not find repo" in f)
    return {
        "actor": raw["me"], "hours": hours,
        "now": raw["now"].isoformat(), "cutoff": raw["cutoff"].isoformat(),
        "follows": raw["follows"], "resolved": raw["resolved"],
        "blocked": blocked, "gone": gone,
        "other": len(fails) - len(blocked) - gone,
        "posts": out,
    }


# ── output ─────────────────────────────────────────────────────────────

def fmt(data):
    ps = data["posts"]
    live = [p for p in ps if not p["ctx"]]
    lines = [f"{len(live)} posts · {len({p['did'] for p in live})} authors · "
             f"{data['cutoff'][11:16]}–{data['now'][11:16]}Z · "
             f"{data['resolved']}/{data['follows']} follows readable"]
    if data["blocked"]:
        lines.append(f"egress-blocked PDSes: {', '.join(data['blocked'])}")
    lines.append("")
    for p in live[:40]:
        tag = "RT " if p["repost"] else ("re " if p["parent"] else "   ")
        lines.append(f"{(p.get('at_event') or p['at'])[11:16]}Z {tag}"
                     f"{p.get('handle', p['did'])[:28]:<28} "
                     + re.sub(r"\s+", " ", p["text"])[:70])
    if len(live) > 40:
        lines.append(f"… {len(live) - 40} more (use --html)")
    return "\n".join(lines)


def to_html(data, path):
    with open(TEMPLATE, encoding="utf8") as f:
        tpl = f.read()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    with open(path, "w", encoding="utf8") as f:
        f.write(tpl.replace("/*__FEED_DATA__*/null", payload))
    return path
