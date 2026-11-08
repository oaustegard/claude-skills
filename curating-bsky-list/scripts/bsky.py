"""The Bluesky calls this skill makes, on urllib alone.

Reads go to the public AppView, except post search, which Bluesky answers only for a signed-in account; that one
signs in as Muninn. Writes are limited to one thing: list items on Muninn's own curate list. Credentials come
from MUNINN_BSKY_HANDLE / MUNINN_BSKY_APP_PASSWORD only. The unprefixed BSKY_* pair in the same environment is
Oskar's and is never read here; `session()` also refuses any account whose DID is not the expected one.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

PUBLIC = "https://public.api.bsky.app/xrpc"
ENTRYWAY = "https://bsky.social"
MUNINN_DID = "did:plc:tc43adcqjhjmtnncm723ztvv"
DISCOVER = "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot"
UA = {"User-Agent": "curating-bsky-list"}


class BskyError(Exception):
    pass


def _send(req, tries=5):
    """One request. Retries transport errors, 429 and 5xx with backoff; other 4xx return None."""
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf8", "replace")
            if e.code == 429 or e.code >= 500:
                last = BskyError(f"HTTP {e.code} {req.full_url.split('?')[0]}: {body}")
                retry = e.headers.get("Retry-After")
                time.sleep(min(60, int(retry)) if retry and retry.isdigit() else 2 ** k)
                continue
            if req.get_method() == "POST":
                raise BskyError(f"HTTP {e.code} {req.full_url}: {body}") from e
            return None
        except (urllib.error.URLError, OSError) as e:
            last = BskyError(f"unreachable {req.full_url.split('?')[0]}: {getattr(e, 'reason', e)}")
            time.sleep(2 ** k)
    raise last


def get(ep, params=None, base=PUBLIC, token=None):
    """GET an XRPC endpoint. `params` may be a dict or a list of pairs (repeated keys)."""
    q = urllib.parse.urlencode(params or {}, doseq=True)
    headers = dict(UA)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _send(urllib.request.Request(f"{base}/{ep}?{q}", headers=headers))


def post(ep, body, base, token):
    return _send(urllib.request.Request(
        f"{base}/{ep}", data=json.dumps(body).encode(), method="POST",
        headers={**UA, "Authorization": f"Bearer {token}", "Content-Type": "application/json"}))


def session(expected_did=MUNINN_DID):
    """Sign in as Muninn. Returns {did, handle, token, pds}."""
    handle = os.environ.get("MUNINN_BSKY_HANDLE", "").strip()
    pw = os.environ.get("MUNINN_BSKY_APP_PASSWORD", "").strip()
    if not handle or not pw:
        raise BskyError("MUNINN_BSKY_HANDLE / MUNINN_BSKY_APP_PASSWORD are not set")
    s = _send(urllib.request.Request(
        f"{ENTRYWAY}/xrpc/com.atproto.server.createSession", method="POST",
        data=json.dumps({"identifier": handle, "password": pw}).encode(),
        headers={**UA, "Content-Type": "application/json"}))
    if s.get("did") != expected_did:
        raise BskyError(f"signed in as {s.get('did')}, expected {expected_did}; refusing to continue")
    pds = ENTRYWAY
    for svc in (s.get("didDoc") or {}).get("service", []):
        if svc.get("id", "").endswith("atproto_pds"):
            pds = svc["serviceEndpoint"].rstrip("/")
    return {"did": s["did"], "handle": s["handle"], "token": s["accessJwt"], "pds": pds}


def now_iso():
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_time(s):
    try:
        return dt.datetime.fromisoformat(s).timestamp()
    except (AttributeError, ValueError):
        return None


# ── reads ──────────────────────────────────────────────────────────────

def paged(ep, params, key, limit=None, base=PUBLIC, token=None, page=100):
    out, cur = [], None
    while True:
        p = dict(params, limit=page)
        if cur:
            p["cursor"] = cur
        d = get(ep, p, base, token)
        if not d:
            break
        out += d.get(key, [])
        cur = d.get("cursor")
        if not cur or not d.get(key) or (limit and len(out) >= limit):
            break
    return out[:limit] if limit else out


def resolve(handle):
    if handle.startswith("did:"):
        return handle
    d = get("com.atproto.identity.resolveHandle", {"handle": handle})
    if not d:
        raise BskyError(f"cannot resolve {handle}")
    return d["did"]


def pds_of(did):
    """The PDS that hosts `did` (did:plc via plc.directory, did:web via its well-known document)."""
    if did.startswith("did:web:"):
        url = f"https://{did[8:]}/.well-known/did.json"
    else:
        url = f"https://plc.directory/{did}"
    doc = _send(urllib.request.Request(url, headers=UA)) or {}
    for svc in doc.get("service", []):
        if svc.get("id", "").endswith("atproto_pds"):
            return svc["serviceEndpoint"].rstrip("/")
    raise BskyError(f"no PDS for {did}")


def list_dids(uri):
    return [it["subject"]["did"] for it in paged("app.bsky.graph.getList", {"list": uri}, "items")]


def follows(actor, limit=3000):
    """An account's follows; [] when the AppView keeps failing for this one account."""
    try:
        return [f["did"] for f in paged("app.bsky.graph.getFollows", {"actor": actor}, "follows", limit)]
    except BskyError:
        return []


def profiles(dids):
    """{did: profile}. A DID the AppView did not return is absent; one whose batch failed maps to None."""
    out = {}
    dids = list(dids)
    for i in range(0, len(dids), 25):
        try:
            d = get("app.bsky.actor.getProfiles", [("actors", x) for x in dids[i:i + 25]])
        except BskyError:
            out.update(dict.fromkeys(dids[i:i + 25]))     # no data, which is not the same as "gone"
            continue
        for pr in (d or {}).get("profiles", []):
            out[pr["did"]] = pr
    return out


def author_posts(did, limit=100):
    """An account's own recent posts and replies, reposts left out. Each: {uri, t, text, reply}.

    None when the AppView refuses the feed (deleted, deactivated or suspended account), which is not the same
    answer as an empty list.
    """
    try:
        d = get("app.bsky.feed.getAuthorFeed", {"actor": did, "limit": min(100, limit), "filter": "posts_with_replies"})
    except BskyError:       # a feed the AppView 500s on, five times running
        return None
    if d is None:
        return None
    out = []
    for it in d.get("feed", []):
        p = it["post"]
        if "reason" in it or p["author"]["did"] != did:
            continue
        rec = p.get("record") or {}
        out.append({"uri": p["uri"], "t": parse_time(rec.get("createdAt") or p.get("indexedAt")),
                    "text": rec.get("text") or "", "reply": bool(rec.get("reply"))})
    return out


def repo_records(did, collection, limit=1000, pds=None):
    """Records of one collection from an account's own repo (public, no AppView in between)."""
    pds = pds or pds_of(did)
    return paged("com.atproto.repo.listRecords", {"repo": did, "collection": collection}, "records", limit,
                 base=f"{pds}/xrpc")


def search_posts(term, since, auth, pages=2, lang="en"):
    """Phrase search over posts since `since` (YYYY-MM-DD), newest first. lang=None searches every language."""
    out, cur = [], None
    query = f'"{term}"' + (f" lang:{lang}" if lang else "") + f" since:{since}"
    for _ in range(pages):
        q = {"q": query, "limit": 100, "sort": "latest"}
        if cur:
            q["cursor"] = cur
        d = get("app.bsky.feed.searchPosts", q, base=f"{auth['pds']}/xrpc", token=auth["token"])
        if not d:
            break
        out += d.get("posts", [])
        cur = d.get("cursor")
        if not cur or not d.get("posts"):
            break
    return out


def discover_posts(n=1200):
    rows = paged("app.bsky.feed.getFeed", {"feed": DISCOVER}, "feed", n)
    return [(r["post"].get("record") or {}).get("text") or "" for r in rows]


def list_feed(list_uri, since_ts, max_pages=30):
    out, cur = [], None
    for _ in range(max_pages):
        p = {"list": list_uri, "limit": 100}
        if cur:
            p["cursor"] = cur
        d = get("app.bsky.feed.getListFeed", p)
        if not d or not d.get("feed"):
            break
        old = False
        for it in d["feed"]:
            t = parse_time(it["post"].get("indexedAt"))
            if t is not None and t < since_ts and "reason" not in it:
                old = True
            out.append(it)
        cur = d.get("cursor")
        if old or not cur:
            break
    return out


# ── writes: listitems on Muninn's own list, nothing else ───────────────

def create_list(auth, name, description):
    r = post("com.atproto.repo.createRecord", {
        "repo": auth["did"], "collection": "app.bsky.graph.list",
        "record": {"$type": "app.bsky.graph.list", "purpose": "app.bsky.graph.defs#curatelist",
                   "name": name, "description": description, "createdAt": now_iso()}},
        f"{auth['pds']}/xrpc", auth["token"])
    return r["uri"]


def own_items(auth, list_uri):
    """{did: listitem uri} for `list_uri`, read from Muninn's repo (the AppView lags writes)."""
    recs = paged("com.atproto.repo.listRecords", {"repo": auth["did"], "collection": "app.bsky.graph.listitem"},
                 "records", base=f"{auth['pds']}/xrpc", token=auth["token"])
    return {r["value"]["subject"]: r["uri"] for r in recs if r["value"].get("list") == list_uri}


def _check_list(auth, list_uri):
    if not list_uri.startswith(f"at://{auth['did']}/app.bsky.graph.list/"):
        raise BskyError(f"{list_uri} is not a list in {auth['did']}'s repo; refusing to write")


def add_items(auth, list_uri, dids):
    _check_list(auth, list_uri)
    have = own_items(auth, list_uri)
    new = [d for d in dict.fromkeys(dids) if d not in have]
    for i in range(0, len(new), 100):
        post("com.atproto.repo.applyWrites", {"repo": auth["did"], "writes": [
            {"$type": "com.atproto.repo.applyWrites#create", "collection": "app.bsky.graph.listitem",
             "value": {"$type": "app.bsky.graph.listitem", "subject": d, "list": list_uri, "createdAt": now_iso()}}
            for d in new[i:i + 100]]}, f"{auth['pds']}/xrpc", auth["token"])
    return new


def remove_items(auth, list_uri, dids):
    _check_list(auth, list_uri)
    have = own_items(auth, list_uri)
    gone = [d for d in dict.fromkeys(dids) if d in have]
    for i in range(0, len(gone), 100):
        post("com.atproto.repo.applyWrites", {"repo": auth["did"], "writes": [
            {"$type": "com.atproto.repo.applyWrites#delete", "collection": "app.bsky.graph.listitem",
             "rkey": have[d].rsplit("/", 1)[1]} for d in gone[i:i + 100]]}, f"{auth['pds']}/xrpc", auth["token"])
    return gone
