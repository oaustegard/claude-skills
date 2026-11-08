"""Durable state for the list, and the insight counts that decide whether exploration members stay.

State is one JSON document in Muninn's config table (key muninn-bsky-list-state, category ops, not boot-loaded),
written over Turso's HTTP pipeline with TURSO_URL / TURSO_TOKEN, so it needs neither the remembering skill nor
the hub's container layer. `--state-file` swaps in a local file (tests, dry runs, a store outage).

Insights are Muninn memories tagged bsky-list-insight. A member's count is the number of live memories in the
window whose text names the member's DID or handle.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

KEY = "muninn-bsky-list-state"
INSIGHT_TAG = "bsky-list-insight"
SOURCE = "skill:curating-bsky-list"


class StoreError(Exception):
    pass


def empty_state():
    return {"version": 1, "list_uri": None, "list_url": None, "created": None, "params": {},
            "members": {}, "removed": {}, "extra_topics": [], "runs": []}


class Turso:
    def __init__(self, url=None, token=None):
        url = (url or os.environ.get("TURSO_URL") or "").strip()
        self.token = (token or os.environ.get("TURSO_TOKEN") or "").strip()
        if not url or not self.token:
            raise StoreError("TURSO_URL / TURSO_TOKEN are not set (or pass --state-file)")
        url = url.replace("libsql://", "https://")
        self.url = (url if url.startswith("http") else "https://" + url).rstrip("/") + "/v2/pipeline"

    def execute(self, sql, args=()):
        stmt = {"sql": sql, "args": [{"type": "null"} if a is None else {"type": "text", "value": str(a)}
                                     for a in args]}
        body = json.dumps({"requests": [{"type": "execute", "stmt": stmt}, {"type": "close"}]}).encode()
        last = None
        for k in range(5):        # cold-start 503s are expected; back off, never treat them as auth failures
            try:
                req = urllib.request.Request(self.url, data=body, headers={
                    "Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                    "User-Agent": "curating-bsky-list"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    res = json.loads(r.read())["results"][0]
                if res.get("type") != "ok":
                    raise StoreError(f"Turso error: {json.dumps(res)[:300]}")
                result = res["response"]["result"]
                cols = [c["name"] for c in result["cols"]]
                return [dict(zip(cols, [c.get("value") for c in row])) for row in result["rows"]]
            except urllib.error.HTTPError as e:
                if e.code < 500:
                    raise StoreError(f"Turso HTTP {e.code}: {e.read()[:200]!r}") from e
                last = StoreError(f"Turso HTTP {e.code}")
            except (urllib.error.URLError, OSError) as e:
                last = StoreError(f"Turso unreachable: {e}")
            time.sleep(2 ** k)
        raise last


class Store:
    """load() / save() of the state document, and insight counts."""

    def __init__(self, state_file=None, version=""):
        self.file = Path(state_file) if state_file else None
        self.db = None if self.file else Turso()
        self.version = version

    def load(self):
        if self.file:
            return json.loads(self.file.read_text()) if self.file.exists() else empty_state()
        rows = self.db.execute("SELECT value FROM config WHERE key = ?", [KEY])
        return json.loads(rows[0]["value"]) if rows else empty_state()

    def save(self, state):
        text = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        if self.file:
            self.file.write_text(text)
            return
        now = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
        # An upsert that leaves boot_load / read_only alone on an existing row: the key is reference data.
        self.db.execute(
            "INSERT INTO config (key, value, category, updated_at, read_only, boot_load, source) "
            "VALUES (?, ?, 'ops', ?, 0, 0, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, "
            "source = excluded.source",
            [KEY, text, now, f"{SOURCE}@{self.version}"])

    def insights(self, since_iso):
        """Live insight memories created since `since_iso`: [{summary, created_at}]. None without a database."""
        if not self.db:
            return None
        return self.db.execute(
            "SELECT summary, created_at FROM memories WHERE deleted_at IS NULL AND tags LIKE ? AND created_at >= ?",
            [f'%"{INSIGHT_TAG}"%', since_iso])


def insight_counts(rows, members, since_by_did=None):
    """{did: count} of insight memories naming each member (DID or @handle), optionally per-member start dates."""
    out = {}
    for did, m in members.items():
        h = (m.get("handle") or "").lower()
        since = (since_by_did or {}).get(did, "")
        n = 0
        for r in rows or []:
            if r["created_at"] < since:
                continue
            s = r["summary"]
            low = s.lower()
            if did in s or (h and (f"@{h}" in low or f"/profile/{h}/" in low)):
                n += 1
        out[did] = n
    return out
