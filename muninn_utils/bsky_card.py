"""
bsky_card.py — Bluesky link card composition (flowing-graph orchestrator).

Same low-level helpers as the prior version (fetch_og_tags, upload_blob,
compute_facets, build_external_embed, create_post), now with a
flowing-graph-based `compose_link_post` and a new `compose_and_post`
that fuses compose+post into one DAG.

Internal shape (issue oaustegard/claude-skills#617):

    fetch_og ──▶ upload_blob_node ──┐
        │                            │
        └──▶ embed_node ◀────────────┘
                  │
    facets_node ──┼──▶ record_node  [terminal of compose_link_post]
                  │         │
                  │         └──▶ post_node  [terminal of compose_and_post]

Wins over imperative:

  - `fetch_og` and `facets_node` parallelize (one network, one local).
  - `validate=must_be_valid_record` enforces the AT Proto record shape
    BEFORE the body of post_node ever fires — no wasted createRecord.
  - `upload_blob_node` failure cleanly SKIPS embed and post — no partial
    post. (Behavior change vs. the prior soft-fail; see #617 win 3.)
  - max_workers=3 on the Flow → the parallel legs run concurrently.

Public API:

    record = compose_link_post(text, url, auth)        # builds record only
    result = compose_and_post(text, url, auth)         # builds AND posts

`result` keys: record, post, og_tags, thumb_blob, facets, detached_failures.
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from urllib.parse import urlparse

from flowing import task, Flow, StepState


# ── OG Tag Extraction ──────────────────────────────────────────────

def fetch_og_tags(url):
    """Fetch a page and extract Open Graph meta tags.

    Returns dict with keys: url, title, description, image.
    Falls back to <title> and meta description if OG tags are absent.
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (bsky-card bot)"
    })
    html = urllib.request.urlopen(req).read().decode("utf-8", errors="replace")

    tags = {"url": url}
    for prop in ["title", "description", "image"]:
        m = _match_og(html, prop)
        if m:
            tags[prop] = m

    if "title" not in tags:
        m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        if m:
            tags["title"] = m.group(1).strip()

    if "description" not in tags:
        m = re.search(
            r'<meta\s+name="description"\s+content="([^"]+)"',
            html, re.IGNORECASE
        )
        if m:
            tags["description"] = m.group(1)

    if tags.get("image", "").startswith("/"):
        parsed = urlparse(url)
        tags["image"] = f"{parsed.scheme}://{parsed.netloc}{tags['image']}"

    return tags


def _match_og(html, prop):
    """Try multiple patterns to extract an og: meta tag value."""
    patterns = [
        rf'<meta\s+(?:property|name)="og:{prop}"\s+content="([^"]+)"',
        rf"<meta\s+(?:property|name)='og:{prop}'\s+content='([^']+)'",
        rf'<meta\s+content="([^"]+)"\s+(?:property|name)="og:{prop}"',
        rf"<meta\s+content='([^']+)'\s+(?:property|name)='og:{prop}'",
    ]
    for pattern in patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


# ── Blob Upload ────────────────────────────────────────────────────

def upload_blob(image_url, auth):
    """Download an image from a URL and upload it as a Bluesky blob.

    Returns blob dict (with $type, ref, mimeType, size) suitable for
    use as embed.external.thumb.
    """
    req = urllib.request.Request(image_url, headers={
        "User-Agent": "Mozilla/5.0 (bsky-card bot)"
    })
    resp = urllib.request.urlopen(req)
    image_data = resp.read()
    content_type = resp.headers.get("Content-Type", "image/png")

    upload_req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
        data=image_data, method="POST",
        headers={
            "Authorization": f"Bearer {auth['access_jwt']}",
            "Content-Type": content_type
        }
    )
    result = json.loads(urllib.request.urlopen(upload_req).read())
    return result["blob"]


# ── Facet Computation ──────────────────────────────────────────────

def compute_facets(text):
    """Find URLs and #hashtags in text and create ATProto facets.

    Returns list of facet dicts with correct UTF-8 byte offsets.
    """
    facets = []

    for match in re.finditer(r'https?://\S+', text):
        url_str = match.group(0)
        while url_str and url_str[-1] in ".,;:!?)\"'":
            url_str = url_str[:-1]
        byte_start, byte_end = _byte_offsets(text, match.start(), url_str)
        facets.append({
            "index": {"byteStart": byte_start, "byteEnd": byte_end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url_str}]
        })

    for match in re.finditer(r'(?<!\w)#(\w+)', text):
        tag = match.group(1)
        full = match.group(0)
        byte_start, byte_end = _byte_offsets(text, match.start(), full)
        facets.append({
            "index": {"byteStart": byte_start, "byteEnd": byte_end},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}]
        })

    return facets


def _byte_offsets(text, char_start, matched_text):
    """Convert character position to UTF-8 byte offsets."""
    prefix_bytes = text[:char_start].encode("utf-8")
    matched_bytes = matched_text.encode("utf-8")
    return len(prefix_bytes), len(prefix_bytes) + len(matched_bytes)


# ── Embed Construction ─────────────────────────────────────────────

def build_external_embed(og_tags, thumb_blob=None):
    """Build an app.bsky.embed.external embed dict from OG tags."""
    external = {
        "uri": og_tags["url"],
        "title": og_tags.get("title", ""),
        "description": og_tags.get("description", ""),
    }
    if thumb_blob:
        external["thumb"] = thumb_blob

    return {
        "$type": "app.bsky.embed.external",
        "external": external
    }


# ── Edge contracts ─────────────────────────────────────────────────

def _must_have_valid_record_inputs(**deps):
    """Edge contract for record_node: validate embed and facets shape.

    Runs against gathered dep values (embed_node, facets_node) BEFORE the
    record body fires. Catches malformed embed (no uri) or non-list facets
    so the post downstream can't fire on a broken card.
    """
    embed = deps.get("embed_node")
    if not isinstance(embed, dict):
        raise ValueError("embed_node missing or not a dict")
    external = embed.get("external") or {}
    if not external.get("uri"):
        raise ValueError("record.embed.external.uri is missing — link card has no target")

    facets = deps.get("facets_node")
    if not isinstance(facets, list):
        raise ValueError("facets_node not a list")


# ── High-Level Composition (flowing graph) ─────────────────────────

def _build_compose_graph(text, url, auth, og_tags=None):
    """Construct the compose-pipeline tasks; return (record_node, fetch_og).

    Tasks are closure-bound to (text, url, auth, og_tags). The caller
    decides which terminal to drive — record_node alone (compose only)
    or post_node downstream (compose + post).
    """
    if url not in text:
        text = f"{text}\n{url}"

    pre_supplied = og_tags

    @task(name="fetch_og")
    def fetch_og():
        if pre_supplied is not None:
            return pre_supplied
        return fetch_og_tags(url)

    @task(name="upload_blob_node", depends_on=[fetch_og])
    def upload_blob_node(fetch_og):
        img = fetch_og.get("image")
        if not img:
            # No image at all is a clean success with a None payload —
            # embed_node proceeds and builds a thumb-less card.
            return None
        # Genuine upload failure raises → embed/post SKIP. (#617 win 3.)
        return upload_blob(img, auth)

    @task(name="facets_node")
    def facets_node():
        return compute_facets(text)

    @task(name="embed_node", depends_on=[upload_blob_node, fetch_og])
    def embed_node(upload_blob_node, fetch_og):
        return build_external_embed(fetch_og, thumb_blob=upload_blob_node)

    @task(
        name="record_node",
        depends_on=[embed_node, facets_node],
        validate=_must_have_valid_record_inputs,
    )
    def record_node(embed_node, facets_node):
        return {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "facets": facets_node,
            "embed": embed_node,
        }

    return {
        "fetch_og": fetch_og,
        "upload_blob_node": upload_blob_node,
        "facets_node": facets_node,
        "embed_node": embed_node,
        "record_node": record_node,
        "_text": text,  # post-URL-append, for callers that need it
    }


def compose_link_post(text, url, auth, og_tags=None):
    """Build a complete post record with link card.

    Runs a flowing graph internally:
      fetch_og + facets_node (parallel) → upload_blob_node → embed_node → record_node

    Returns the assembled record (same shape as the prior imperative version).
    Raises on graph failure with the originating error attached.
    """
    nodes = _build_compose_graph(text, url, auth, og_tags)
    flow = Flow(nodes["record_node"], max_workers=3)
    flow.run()

    record_state = flow.results.get(nodes["record_node"].name)
    if record_state is None or record_state.state != StepState.SUCCEEDED:
        # Surface the originating failure rather than the SKIP cascade.
        for r in flow.results.values():
            if r.state == StepState.FAILED and r.error is not None:
                raise RuntimeError(
                    f"compose_link_post failed at {r.name}: {r.error}"
                ) from r.error
        raise RuntimeError(
            f"compose_link_post: record_node ended in {record_state.state.value}"
        )
    return record_state.value


def compose_and_post(text, url, auth, og_tags=None):
    """Build the record AND post it on Bluesky in one flowing graph.

    Returns:
        dict with keys: record, post, og_tags, thumb_blob, facets,
        detached_failures (always empty list — included for API symmetry
        with publish_and_announce).

    Raises on hard failure of the main chain.
    """
    nodes = _build_compose_graph(text, url, auth, og_tags)

    @task(name="post_node", depends_on=[nodes["record_node"]])
    def post_node(record_node):
        return create_post(record_node, auth)

    flow = Flow(post_node, max_workers=3)
    flow.run()

    post_state = flow.results.get(post_node.name)
    if post_state is None or post_state.state != StepState.SUCCEEDED:
        for r in flow.results.values():
            if r.state == StepState.FAILED and r.error is not None:
                raise RuntimeError(
                    f"compose_and_post failed at {r.name}: {r.error}"
                ) from r.error
        raise RuntimeError(
            f"compose_and_post: post_node ended in {post_state.state.value}"
        )

    def _val(td):
        r = flow.results.get(td.name)
        if r is None or r.state != StepState.SUCCEEDED:
            return None
        return r.value

    return {
        "record": _val(nodes["record_node"]),
        "post": _val(post_node),
        "og_tags": _val(nodes["fetch_og"]),
        "thumb_blob": _val(nodes["upload_blob_node"]),
        "facets": _val(nodes["facets_node"]),
        "detached_failures": [],
    }


def create_post(record, auth):
    """Submit a post record to Bluesky.

    Returns dict with uri, cid, url, rkey.
    """
    data = json.dumps({
        "repo": auth["did"],
        "collection": "app.bsky.feed.post",
        "record": record
    }).encode()

    req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        data=data, method="POST",
        headers={
            "Authorization": f"Bearer {auth['access_jwt']}",
            "Content-Type": "application/json"
        }
    )
    result = json.loads(urllib.request.urlopen(req).read())

    post_uri = result["uri"]
    rkey = post_uri.split("/")[-1]
    handle = auth.get("handle", auth["did"])
    bsky_url = f"https://bsky.app/profile/{handle}/post/{rkey}"

    print(f"  ✓ Posted: {bsky_url}")
    return {
        "uri": post_uri,
        "cid": result["cid"],
        "url": bsky_url,
        "rkey": rkey
    }
