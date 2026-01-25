#!/usr/bin/env python3
"""Bluesky API client for browsing posts, users, feeds, and firehose."""

import os
import requests
import subprocess
import json
import re
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

BASE = "https://api.bsky.app/xrpc"  # Public AppView for unauthenticated reads
PDS_BASE = "https://bsky.social/xrpc"  # PDS for authenticated requests

# Module-level session cache (memory only, never persisted)
_session_cache: Dict[str, Any] = {}


def _create_session() -> Optional[Dict[str, Any]]:
    """Create authenticated session using environment credentials.

    Looks for BSKY_HANDLE and BSKY_APP_PASSWORD environment variables.
    App passwords can be created at: Settings → Privacy and Security → App Passwords

    Returns:
        Session dict with accessJwt, refreshJwt, did, handle, or None if no credentials
    """
    global _session_cache

    handle = os.environ.get("BSKY_HANDLE", "").strip()
    app_password = os.environ.get("BSKY_APP_PASSWORD", "").strip()

    if not handle or not app_password:
        return None

    try:
        r = requests.post(
            f"{PDS_BASE}/com.atproto.server.createSession",
            json={"identifier": handle, "password": app_password},
            timeout=10
        )
        r.raise_for_status()
        session = r.json()
        # Store creation time for token expiry tracking
        session["_created_at"] = time.time()
        _session_cache = session
        return session
    except requests.RequestException:
        # Failed auth - return None to fall back to public access
        return None


def _refresh_session() -> Optional[Dict[str, Any]]:
    """Refresh an expired access token using the refresh token.

    Returns:
        Updated session dict or None if refresh failed
    """
    global _session_cache

    refresh_jwt = _session_cache.get("refreshJwt")
    if not refresh_jwt:
        return None

    try:
        r = requests.post(
            f"{PDS_BASE}/com.atproto.server.refreshSession",
            headers={"Authorization": f"Bearer {refresh_jwt}"},
            timeout=10
        )
        r.raise_for_status()
        session = r.json()
        session["_created_at"] = time.time()
        _session_cache = session
        return session
    except requests.RequestException:
        # Refresh failed - clear cache and fall back to public access
        _session_cache = {}
        return None


def _get_session() -> Optional[Dict[str, Any]]:
    """Get valid session, refreshing if needed.

    Access tokens expire after ~2 hours. This function checks if we have
    a cached session, refreshes if expired, or creates new if needed.

    Returns:
        Valid session dict or None
    """
    global _session_cache

    if not _session_cache:
        return _create_session()

    # Check if access token might be expired (~2 hours = 7200 seconds)
    # Refresh 5 minutes early to avoid edge cases
    created_at = _session_cache.get("_created_at", 0)
    if time.time() - created_at > 7000:
        refreshed = _refresh_session()
        if refreshed:
            return refreshed
        # If refresh failed, try creating new session
        return _create_session()

    return _session_cache


def _auth_headers() -> Dict[str, str]:
    """Get authorization headers if authenticated session available.

    Returns:
        Dict with Authorization header if authenticated, empty dict otherwise
    """
    session = _get_session()
    if session and "accessJwt" in session:
        return {"Authorization": f"Bearer {session['accessJwt']}"}
    return {}


def _get_base_and_headers() -> tuple[str, Dict[str, str]]:
    """Get appropriate base URL and headers based on auth state.

    When authenticated, uses PDS endpoint (bsky.social) with auth headers.
    When not authenticated, uses public AppView (api.bsky.app) without headers.

    Returns:
        Tuple of (base_url, headers_dict)
    """
    session = _get_session()
    if session and "accessJwt" in session:
        return PDS_BASE, {"Authorization": f"Bearer {session['accessJwt']}"}
    return BASE, {}


def is_authenticated() -> bool:
    """Check if currently authenticated with Bluesky.

    Returns:
        True if valid session exists, False otherwise
    """
    session = _get_session()
    return session is not None and "accessJwt" in session


def get_authenticated_user() -> Optional[str]:
    """Get the handle of the currently authenticated user.

    Returns:
        Handle string if authenticated, None otherwise
    """
    session = _get_session()
    if session:
        return session.get("handle")
    return None


def clear_session() -> None:
    """Clear the cached session. Useful for testing or switching accounts."""
    global _session_cache
    _session_cache = {}


def get_profile(handle: str) -> Dict[str, Any]:
    """Get user profile info.

    Args:
        handle: Bluesky handle (with or without @)

    Returns:
        Dict with handle, display_name, description, followers, following, posts, did
    """
    handle = handle.lstrip("@")
    base, headers = _get_base_and_headers()
    r = requests.get(
        f"{base}/app.bsky.actor.getProfile",
        params={"actor": handle},
        headers=headers
    )
    r.raise_for_status()
    data = r.json()
    return {
        "handle": data.get("handle"),
        "display_name": data.get("displayName"),
        "description": data.get("description"),
        "followers": data.get("followersCount"),
        "following": data.get("followsCount"),
        "posts": data.get("postsCount"),
        "did": data.get("did"),
    }


def get_user_posts(handle: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent posts from a user.

    Args:
        handle: Bluesky handle (with or without @)
        limit: Max posts to return (default 20, max 100)

    Returns:
        List of post dicts
    """
    handle = handle.lstrip("@")
    base, headers = _get_base_and_headers()
    r = requests.get(
        f"{base}/app.bsky.feed.getAuthorFeed",
        params={"actor": handle, "limit": min(limit, 100), "filter": "posts_no_replies"},
        headers=headers
    )
    r.raise_for_status()
    return [_parse_post(item["post"]) for item in r.json().get("feed", [])]


def search_posts(
    query: str,
    author: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 25
) -> List[Dict[str, Any]]:
    """Search posts with advanced filters.

    Query can include: from:user mentions:user #tag domain:site lang:xx since:YYYY-MM-DD until:YYYY-MM-DD

    Args:
        query: Search query (supports advanced syntax)
        author: Filter to specific author handle (optional)
        since: Start date YYYY-MM-DD (optional)
        until: End date YYYY-MM-DD (optional)
        lang: Language code like 'en' (optional)
        limit: Max results (default 25, max 100)

    Returns:
        List of post dicts
    """
    parts = [query] if query else []
    if author:
        parts.append(f"from:{author.lstrip('@')}")
    if lang:
        parts.append(f"lang:{lang}")
    if since:
        parts.append(f"since:{since}")
    if until:
        parts.append(f"until:{until}")

    base, headers = _get_base_and_headers()
    r = requests.get(
        f"{base}/app.bsky.feed.searchPosts",
        params={"q": " ".join(parts), "limit": min(limit, 100)},
        headers=headers
    )
    r.raise_for_status()
    return [_parse_post(p) for p in r.json().get("posts", [])]


def get_feed_posts(feed_uri: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get posts from a feed or list.

    Accepts:
    - List URLs: https://bsky.app/profile/austegard.com/lists/3lankcdrlip2f
    - Feed URLs: https://bsky.app/profile/did:plc:xxx/feed/feedname
    - AT-URIs: at://did:plc:xxx/app.bsky.graph.list/xyz

    Args:
        feed_uri: Feed/list URL or AT-URI
        limit: Max posts (default 20, max 100)

    Returns:
        List of post dicts
    """
    # Extract AT-URI from URL if needed
    if feed_uri.startswith("http"):
        uri = _url_to_aturi(feed_uri)
    else:
        uri = feed_uri

    # Determine if it's a list or feed based on collection type
    # Auth is especially important for personalized feeds
    base, headers = _get_base_and_headers()

    if "app.bsky.graph.list" in uri:
        r = requests.get(
            f"{base}/app.bsky.feed.getListFeed",
            params={"list": uri, "limit": min(limit, 100)},
            headers=headers
        )
    else:
        r = requests.get(
            f"{base}/app.bsky.feed.getFeed",
            params={"feed": uri, "limit": min(limit, 100)},
            headers=headers
        )

    r.raise_for_status()
    return [_parse_post(item["post"]) for item in r.json().get("feed", [])]


def sample_firehose(duration: int = 10, filter: Optional[str] = None) -> Dict[str, Any]:
    """Sample the Bluesky firehose for trending topics.

    Prerequisites: Node.js with ws and https-proxy-agent packages
    Run once per session: cd /home/claude && npm install ws https-proxy-agent 2>/dev/null

    Args:
        duration: Sampling duration in seconds (default 10)
        filter: Optional term to filter posts (case-insensitive)

    Returns:
        Dict with topWords, topPhrases, entities, samplePosts, stats
    """
    script_dir = Path(__file__).parent  # browsing-bluesky/scripts/
    zeitgeist_script = script_dir / "zeitgeist-sample.js"

    cmd = ["node", str(zeitgeist_script), "--duration", str(duration)]
    if filter:
        cmd.extend(["--filter", filter])

    import os
    env = os.environ.copy()
    env["NODE_PATH"] = "/home/claude/node_modules"

    # Redirect stderr to devnull to prevent progress output from interfering
    with open(os.devnull, 'w') as devnull:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=devnull,
                                text=True, check=True, env=env)

    return json.loads(result.stdout)


def get_thread(post_uri_or_url: str, depth: int = 6, parent_height: int = 80) -> Dict[str, Any]:
    """Get a post with its full thread context (parents and replies).

    Args:
        post_uri_or_url: AT-URI or bsky.app URL to a post
        depth: How many levels of replies to fetch (default 6, max 1000)
        parent_height: How many parent posts to fetch (default 80, max 1000)

    Returns:
        Dict with 'post' (the target), 'parent' chain, and 'replies' tree
    """
    uri = _ensure_post_uri(post_uri_or_url)
    r = requests.get(f"{BASE}/app.bsky.feed.getPostThread", params={
        "uri": uri,
        "depth": min(depth, 1000),
        "parentHeight": min(parent_height, 1000)
    })
    r.raise_for_status()
    return _parse_thread(r.json().get("thread", {}))


def get_quotes(post_uri_or_url: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Get posts that quote a specific post.

    Args:
        post_uri_or_url: AT-URI or bsky.app URL to the quoted post
        limit: Max results (default 25, max 100)

    Returns:
        List of quote post dicts
    """
    uri = _ensure_post_uri(post_uri_or_url)
    r = requests.get(f"{BASE}/app.bsky.feed.getQuotes", params={
        "uri": uri,
        "limit": min(limit, 100)
    })
    r.raise_for_status()
    return [_parse_post(p) for p in r.json().get("posts", [])]


def get_likes(post_uri_or_url: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get users who liked a post.

    Args:
        post_uri_or_url: AT-URI or bsky.app URL
        limit: Max results (default 50, max 100)

    Returns:
        List of actor dicts with handle, display_name, did
    """
    uri = _ensure_post_uri(post_uri_or_url)
    r = requests.get(f"{BASE}/app.bsky.feed.getLikes", params={
        "uri": uri,
        "limit": min(limit, 100)
    })
    r.raise_for_status()
    return [_parse_actor(like["actor"]) for like in r.json().get("likes", [])]


def get_reposts(post_uri_or_url: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get users who reposted a post.

    Args:
        post_uri_or_url: AT-URI or bsky.app URL
        limit: Max results (default 50, max 100)

    Returns:
        List of actor dicts
    """
    uri = _ensure_post_uri(post_uri_or_url)
    r = requests.get(f"{BASE}/app.bsky.feed.getRepostedBy", params={
        "uri": uri,
        "limit": min(limit, 100)
    })
    r.raise_for_status()
    return [_parse_actor(a) for a in r.json().get("repostedBy", [])]


def get_followers(handle: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get accounts following a user.

    Args:
        handle: Bluesky handle (with or without @)
        limit: Max results (default 50, max 100)

    Returns:
        List of actor dicts
    """
    handle = handle.lstrip("@")
    r = requests.get(f"{BASE}/app.bsky.graph.getFollowers", params={
        "actor": handle,
        "limit": min(limit, 100)
    })
    r.raise_for_status()
    return [_parse_actor(f) for f in r.json().get("followers", [])]


def get_following(handle: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get accounts a user follows.

    Args:
        handle: Bluesky handle (with or without @)
        limit: Max results (default 50, max 100)

    Returns:
        List of actor dicts
    """
    handle = handle.lstrip("@")
    r = requests.get(f"{BASE}/app.bsky.graph.getFollows", params={
        "actor": handle,
        "limit": min(limit, 100)
    })
    r.raise_for_status()
    return [_parse_actor(f) for f in r.json().get("follows", [])]


def search_users(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Search for users by handle, display name, or bio.

    Args:
        query: Search terms
        limit: Max results (default 25, max 100)

    Returns:
        List of actor dicts with profile info
    """
    r = requests.get(f"{BASE}/app.bsky.actor.searchActors", params={
        "q": query,
        "limit": min(limit, 100)
    })
    r.raise_for_status()
    return [_parse_actor(a) for a in r.json().get("actors", [])]


def _parse_post(post: Dict) -> Dict[str, Any]:
    """Extract useful fields from post object."""
    record = post.get("record", {})
    author = post.get("author", {})
    uri_parts = post.get("uri", "").split("/")

    return {
        "uri": post.get("uri"),
        "text": record.get("text", ""),
        "created_at": record.get("createdAt"),
        "author_handle": author.get("handle"),
        "author_name": author.get("displayName"),
        "likes": post.get("likeCount", 0),
        "reposts": post.get("repostCount", 0),
        "replies": post.get("replyCount", 0),
        "url": f"https://bsky.app/profile/{author.get('handle')}/post/{uri_parts[-1]}" if uri_parts else None,
    }


def _url_to_aturi(url: str) -> str:
    """Convert bsky.app URL to AT-URI."""
    # Example: https://bsky.app/profile/austegard.com/lists/3lankcdrlip2f
    # -> at://did:plc:xxx/app.bsky.graph.list/3lankcdrlip2f

    # Extract handle/did and resource ID
    match = re.match(r"https://bsky\.app/profile/([^/]+)/(lists|feed)/([^/?]+)", url)
    if not match:
        raise ValueError(f"Invalid bsky.app URL: {url}")

    actor, resource_type, resource_id = match.groups()

    # Resolve handle to DID if needed
    if not actor.startswith("did:"):
        profile = get_profile(actor)
        did = profile["did"]
    else:
        did = actor

    # Map resource type to collection
    collection = {
        "lists": "app.bsky.graph.list",
        "feed": "app.bsky.feed.generator"
    }[resource_type]

    return f"at://{did}/{collection}/{resource_id}"


def _ensure_post_uri(uri_or_url: str) -> str:
    """Convert bsky.app post URL to AT-URI if needed."""
    if uri_or_url.startswith("at://"):
        return uri_or_url
    if uri_or_url.startswith("http"):
        return _url_to_post_uri(uri_or_url)
    raise ValueError(f"Invalid post reference: {uri_or_url}")


def _url_to_post_uri(url: str) -> str:
    """Convert bsky.app/profile/X/post/Y to AT-URI."""
    match = re.match(r"https://bsky\.app/profile/([^/]+)/post/([^/?]+)", url)
    if not match:
        raise ValueError(f"Invalid post URL: {url}")
    actor, rkey = match.groups()

    if not actor.startswith("did:"):
        profile = get_profile(actor)
        did = profile["did"]
    else:
        did = actor

    return f"at://{did}/app.bsky.feed.post/{rkey}"


def _parse_actor(actor: Dict) -> Dict[str, Any]:
    """Extract useful fields from actor object."""
    return {
        "handle": actor.get("handle"),
        "display_name": actor.get("displayName"),
        "did": actor.get("did"),
        "description": actor.get("description"),
        "avatar": actor.get("avatar"),
        "followers": actor.get("followersCount"),
        "following": actor.get("followsCount"),
    }


def _parse_thread(thread: Dict, depth: int = 0) -> Dict[str, Any]:
    """Parse thread response into clean structure."""
    result = {}

    if "post" in thread:
        result["post"] = _parse_post(thread["post"])
        result["post"]["quote_count"] = thread["post"].get("quoteCount", 0)

    if "parent" in thread:
        result["parent"] = _parse_thread(thread["parent"], depth + 1)

    if "replies" in thread:
        result["replies"] = [_parse_thread(r, depth + 1) for r in thread["replies"]]

    return result
