"""
blog_publish.py — Blog post publishing protocol (flowing-graph orchestrator).

Same public API as the prior imperative version, but `publish_and_announce`
is now a `flowing` DAG internally. The wins:

  - The deploy poll is `retry_until=`, not a hand-rolled `while time.time()` loop.
  - The feed-update gate is structural (`when=`), not an `if` in the orchestrator.
  - Bsky announce + engagement-link are detached side-effects: callers get the
    page URL the moment the deploy lands; bsky failure lands in
    `flow.detached_failures`, never bubbling up as a publish failure.
  - The 300-grapheme bsky limit is enforced as `validate=` BEFORE the post
    fires — no wasted createRecord on a too-long draft.

See issue oaustegard/claude-skills#616 for the rationale.

Public API (unchanged):

    from blog_publish import publish_and_announce, bsky_auth

    auth = bsky_auth()
    result = publish_and_announce(
        path="blog/my-post.html",
        content=html,
        bsky_text="New post — check it out",
        auth=auth,
        feed_entry={...},
    )

`result` keys:
    page_url       — the canonical URL of the published page
    commit_sha     — sha of the page commit
    feed_sha       — sha of the feed commit (None if no feed)
    deployed       — bool: did GH Pages serve the URL within the budget?
    bsky_post      — dict with uri/cid/url/rkey, or None if SKIPPED/FAILED
    update_sha     — sha of the engagement-link commit, or None
    detached_failures — list of (name, error) for any backgrounded failure

The bsky chain is detached: a failure there populates `detached_failures`
but does NOT raise. Callers that need a hard error on bsky failure should
inspect `result["detached_failures"]`.
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from bsky_card import compose_link_post, create_post
from bsky_limit import fits as _bsky_fits, BSKY_LIMIT
from flowing import task, Flow, StepState


# ── Bluesky auth ───────────────────────────────────────────────────

def bsky_auth(handle_var="MUNINN_BSKY_HANDLE", password_var="MUNINN_BSKY_APP_PASSWORD"):
    """Authenticate with Bluesky. Returns auth dict.

    Defaults to Muninn's credentials. For Oskar's account:
        bsky_auth(handle_var="BSKY_HANDLE", password_var="BSKY_APP_PASSWORD")
    """
    handle = os.environ[handle_var]
    password = os.environ[password_var]
    payload = json.dumps({
        "identifier": handle,
        "password": password,
    }).encode()
    req = urllib.request.Request(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    session = json.loads(urllib.request.urlopen(req).read())
    print(f"  ✓ Authenticated as {session['handle']}")
    return {"access_jwt": session["accessJwt"], "did": session["did"], "handle": session["handle"]}


# ── GitHub helpers ─────────────────────────────────────────────────

_MUNINN_REPO = "oaustegard/muninn.austegard.com"
_MUNINN_BASE = "https://muninn.austegard.com"

def _gh_token():
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _gh_api(method, endpoint, data=None):
    token = _gh_token()
    url = f"https://api.github.com{endpoint}" if endpoint.startswith("/") else endpoint
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "User-Agent": "muninn-raven",
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json",
    })
    return json.loads(urllib.request.urlopen(req).read())


def _gh_raw(repo, path, ref="main"):
    """Get raw file content from GitHub."""
    token = _gh_token()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}",
        headers={
            "User-Agent": "muninn-raven",
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw",
        },
    )
    return urllib.request.urlopen(req).read().decode("utf-8")


def publish_page(repo, path, content, message=None):
    """Commit a single file to GitHub Pages repo. Returns commit SHA."""
    if not message:
        message = f"Publish {path}"

    ref = _gh_api("GET", f"/repos/{repo}/git/refs/heads/main")
    ref_sha = ref["object"]["sha"]
    commit = _gh_api("GET", f"/repos/{repo}/git/commits/{ref_sha}")
    tree_sha = commit["tree"]["sha"]

    blob = _gh_api("POST", f"/repos/{repo}/git/blobs",
                    {"content": content, "encoding": "utf-8"})

    tree = _gh_api("POST", f"/repos/{repo}/git/trees", {
        "base_tree": tree_sha,
        "tree": [{"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}],
    })

    new_commit = _gh_api("POST", f"/repos/{repo}/git/commits", {
        "message": message, "tree": tree["sha"], "parents": [ref_sha],
    })

    _gh_api("PATCH", f"/repos/{repo}/git/refs/heads/main",
            {"sha": new_commit["sha"]})

    return new_commit["sha"]


# ── Atom feed maintenance ──────────────────────────────────────────

ATOM_NS = "http://www.w3.org/2005/Atom"

def update_feed(repo, feed_path, page_url, entry, message=None):
    """Add an entry to the Atom feed and update the <updated> timestamp.

    entry dict keys:
        title (required): Post title
        summary (required): Brief description
        published (optional): ISO datetime, defaults to now
        updated (optional): ISO datetime, defaults to published

    Returns commit SHA.
    """
    ET.register_namespace("", ATOM_NS)

    current_xml = _gh_raw(repo, feed_path)
    root = ET.fromstring(current_xml)

    ns = {"atom": ATOM_NS}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    published = entry.get("published", now)
    updated = entry.get("updated", published)

    feed_updated = root.find("atom:updated", ns)
    if feed_updated is not None:
        feed_updated.text = now

    new_entry = ET.SubElement(root, f"{{{ATOM_NS}}}entry")
    ET.SubElement(new_entry, f"{{{ATOM_NS}}}title").text = entry["title"]

    link = ET.SubElement(new_entry, f"{{{ATOM_NS}}}link")
    link.set("href", page_url)
    link.set("rel", "alternate")
    link.set("type", "text/html")

    ET.SubElement(new_entry, f"{{{ATOM_NS}}}id").text = page_url
    ET.SubElement(new_entry, f"{{{ATOM_NS}}}published").text = published
    ET.SubElement(new_entry, f"{{{ATOM_NS}}}updated").text = updated
    ET.SubElement(new_entry, f"{{{ATOM_NS}}}summary").text = entry["summary"]

    output = _pretty_feed(root, ns)

    if not message:
        message = f"Add feed entry: {entry['title']}"

    sha = publish_page(repo, feed_path, output, message=message)
    print(f"  ✓ Feed updated with: {entry['title']}")
    return sha


def _pretty_feed(root, ns):
    """Serialize Atom feed with readable formatting."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>']
    lines.append('<feed xmlns="http://www.w3.org/2005/Atom">')

    for child in root:
        tag = child.tag.replace(f"{{{ATOM_NS}}}", "")
        if tag == "entry":
            continue
        if len(child) == 0 and child.text:
            attribs = "".join(f' {k}="{v}"' for k, v in child.attrib.items())
            lines.append(f"  <{tag}{attribs}>{child.text}</{tag}>")
        elif len(child) == 0:
            attribs = "".join(f' {k}="{v}"' for k, v in child.attrib.items())
            lines.append(f"  <{tag}{attribs}/>")
        else:
            attribs = "".join(f' {k}="{v}"' for k, v in child.attrib.items())
            inner = ""
            for sub in child:
                stag = sub.tag.replace(f"{{{ATOM_NS}}}", "")
                inner += f"<{stag}>{sub.text or ''}</{stag}>"
            lines.append(f"  <{tag}{attribs}>{inner}</{tag}>")

    for entry in root.findall("atom:entry", ns):
        lines.append("")
        lines.append("  <entry>")
        for child in entry:
            tag = child.tag.replace(f"{{{ATOM_NS}}}", "")
            attribs = "".join(f' {k}="{v}"' for k, v in child.attrib.items())
            if child.text:
                lines.append(f"    <{tag}{attribs}>{child.text}</{tag}>")
            else:
                lines.append(f"    <{tag}{attribs}/>")
        lines.append("  </entry>")

    lines.append("")
    lines.append("</feed>")
    lines.append("")
    return "\n".join(lines)


# ── Deploy probing ─────────────────────────────────────────────────

def _probe_url(url: str) -> bool:
    """One HEAD probe. True iff status 200."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        resp = urllib.request.urlopen(req)
        return resp.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False


def wait_for_deploy(url, timeout=120, poll_interval=10):
    """Poll a URL until it returns 200. Returns True on success.

    Retained for backward compat / step-by-step usage. The flowing
    orchestrator in `publish_and_announce` uses the `retry_until=` primitive
    instead, which is the same behavior expressed structurally.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _probe_url(url):
            print(f"  ✓ {url} is live")
            return True
        remaining = int(deadline - time.time())
        print(f"  … waiting for deploy ({remaining}s remaining)")
        time.sleep(poll_interval)
    print(f"  ✗ Timeout waiting for {url}")
    return False


# ── Engagement linking ─────────────────────────────────────────────

_SITE_TO_REPO = {
    "austegard.com": "oaustegard/oaustegard.github.io",
    "muninn.austegard.com": "oaustegard/muninn.austegard.com",
}


def _bsky_url_to_at_uri(bsky_url):
    """Convert https://bsky.app/profile/HANDLE/post/RKEY → at://DID/app.bsky.feed.post/RKEY."""
    if bsky_url.startswith("at://"):
        return bsky_url
    m = re.match(r"https?://bsky\.app/profile/([^/]+)/post/([^/]+)", bsky_url)
    if not m:
        raise ValueError(f"Not a bsky.app post URL: {bsky_url}")
    handle, rkey = m.group(1), m.group(2)
    resp = urllib.request.urlopen(
        f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle={handle}"
    )
    did = json.loads(resp.read())["did"]
    return f"at://{did}/app.bsky.feed.post/{rkey}"


def link_engagement(repo, path, bsky_uri):
    """Update a page's bsky:uri meta tag and noscript link for the engagement widget.

    bsky_uri: AT URI or bsky.app URL (auto-resolved to AT URI for meta tag).
    Returns commit SHA or None if nothing to update.
    """
    at_uri = _bsky_url_to_at_uri(bsky_uri)
    m = re.match(r"at://([^/]+)/app\.bsky\.feed\.post/(.+)", at_uri)
    bsky_app_url = f"https://bsky.app/profile/{m.group(1)}/post/{m.group(2)}" if m else bsky_uri

    current = _gh_raw(repo, path)
    updated = current

    updated = re.sub(
        r'(<meta\s+name="bsky:uri"\s+content=")[^"]*(")',
        rf'\g<1>{at_uri}\2',
        updated, count=1,
    )

    updated = re.sub(
        r'(<a\s+href=")https://bsky\.app/profile/[^"]*(">\s*Discuss on Bluesky)',
        rf'\g<1>{bsky_app_url}\2',
        updated, count=1,
    )

    updated = re.sub(
        r'data-bsky-uri="[^"]*"',
        f'data-bsky-uri="{at_uri}"',
        updated, count=1,
    )

    if updated == current:
        print("  ⚠ No bsky:uri meta tag or engagement attributes found")
        return None

    sha = publish_page(repo, path, updated,
                       message=f"Link Bluesky engagement for {path}")
    print(f"  ✓ Updated {path} with Bluesky URI")
    return sha


def link_bsky(page_url, bsky_url):
    """Link a blog post to its Bluesky discussion post.

    Infers repo from domain. Returns commit SHA.
    """
    from urllib.parse import urlparse
    parsed = urlparse(page_url)
    domain = parsed.netloc
    repo = _SITE_TO_REPO.get(domain)
    if not repo:
        raise ValueError(f"Unknown domain {domain}. Known: {list(_SITE_TO_REPO.keys())}")
    path = parsed.path.lstrip("/")
    return link_engagement(repo, path, bsky_url)


# ── Full protocol (flowing graph) ──────────────────────────────────

# Default poll cadence for the GH Pages deploy. Retained at 10s × 12 to match
# the prior wait_for_deploy(timeout=120, poll_interval=10) budget.
_DEPLOY_POLL_MS = 10_000
_DEPLOY_RETRIES = 12


def publish_and_announce(path, content, bsky_text, auth,
                         repo=_MUNINN_REPO,
                         site_base=_MUNINN_BASE,
                         feed_path="feed.xml",
                         feed_entry=None,
                         commit_message=None,
                         skip_deploy_wait=False):
    """Publish page → wait for deploy → update feed; bsky chain runs detached.

    Internal shape (flowing graph):

        publish_page_node ──▶ wait_for_deploy_node ──▶ update_feed_node  [terminal]
                                       │
                                       └──▶ announce_bsky [detached]
                                                  │
                                                  └──▶ link_engagement_node [detached]

    The bsky leg is auto-discovered (v1.2 flowing) — its dependency
    (wait_for_deploy_node) is reachable from the terminal, so the runner picks
    it up without an explicit terminal of its own. Failures there land in
    `flow.detached_failures` and the function still returns the page URL.

    See issue oaustegard/claude-skills#616.
    """
    url = f"{site_base}/{path}"

    @task(name="publish_page_node")
    def publish_page_node():
        sha = publish_page(repo, path, content, commit_message)
        print(f"  ✓ Page committed: {sha[:10]}")
        return {"commit_sha": sha, "url": url}

    @task(
        name="wait_for_deploy_node",
        depends_on=[publish_page_node],
        retry=_DEPLOY_RETRIES,
        retry_backoff_base_ms=_DEPLOY_POLL_MS,
        retry_max_backoff_ms=_DEPLOY_POLL_MS,
        retry_until=lambda r: r["deployed"],
    )
    def wait_for_deploy_node(publish_page_node):
        if skip_deploy_wait:
            return {"deployed": True, "skipped": True, "url": url}
        live = _probe_url(url)
        if live:
            print(f"  ✓ {url} is live")
        return {"deployed": live, "url": url}

    @task(
        name="update_feed_node",
        depends_on=[wait_for_deploy_node],
        when=lambda **_: feed_path is not None and feed_entry is not None,
    )
    def update_feed_node(wait_for_deploy_node):
        sha = update_feed(repo, feed_path, url, feed_entry)
        return {"feed_sha": sha}

    def must_be_under_bsky_limit(**deps):
        if not _bsky_fits(bsky_text):
            raise ValueError(
                f"bsky_text exceeds {BSKY_LIMIT} graphemes — would be rejected by AT Proto. "
                "Trim before calling, or use bsky_limit.truncate()."
            )

    @task(
        name="announce_bsky",
        depends_on=[wait_for_deploy_node],
        validate=must_be_under_bsky_limit,
        detached=True,
    )
    def announce_bsky(wait_for_deploy_node):
        record = compose_link_post(bsky_text, url, auth)
        post = create_post(record, auth)
        return post

    @task(
        name="link_engagement_node",
        depends_on=[announce_bsky],
        detached=True,
    )
    def link_engagement_node(announce_bsky):
        sha = link_engagement(repo, path, announce_bsky["url"])
        return {"update_sha": sha}

    flow = Flow(update_feed_node)
    flow.run()

    def _val(td, key=None, default=None):
        r = flow.results.get(td.name)
        if r is None or r.state != StepState.SUCCEEDED:
            return default
        return r.value if key is None else r.value.get(key, default)

    bsky_post = _val(announce_bsky)
    detached_failures = [(r.name, str(r.error)) for r in flow.detached_failures]

    print(f"\n✓ Done!")
    print(f"  Page: {url}")
    if bsky_post:
        print(f"  Post: {bsky_post['url']}")
    if detached_failures:
        print(f"  Detached failures: {detached_failures}")

    return {
        "page_url": url,
        "commit_sha": _val(publish_page_node, "commit_sha"),
        "deployed": bool(_val(wait_for_deploy_node, "deployed", default=False)),
        "feed_sha": _val(update_feed_node, "feed_sha"),
        "bsky_post": bsky_post,
        "update_sha": _val(link_engagement_node, "update_sha"),
        "detached_failures": detached_failures,
    }
