#!/usr/bin/env python3
"""Bluesky API client for browsing posts, users, feeds, and firehose."""

import requests
import subprocess
import json
import re
from typing import Optional, List, Dict, Any
from pathlib import Path

BASE = "https://api.bsky.app/xrpc"  # NOT public.api.bsky.app


def get_profile(handle: str) -> Dict[str, Any]:
    """Get user profile info.

    Args:
        handle: Bluesky handle (with or without @)

    Returns:
        Dict with handle, display_name, description, followers, following, posts, did
    """
    handle = handle.lstrip("@")
    r = requests.get(f"{BASE}/app.bsky.actor.getProfile", params={"actor": handle})
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
    r = requests.get(
        f"{BASE}/app.bsky.feed.getAuthorFeed",
        params={"actor": handle, "limit": min(limit, 100), "filter": "posts_no_replies"}
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

    r = requests.get(
        f"{BASE}/app.bsky.feed.searchPosts",
        params={"q": " ".join(parts), "limit": min(limit, 100)}
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
    if "app.bsky.graph.list" in uri:
        r = requests.get(
            f"{BASE}/app.bsky.feed.getListFeed",
            params={"list": uri, "limit": min(limit, 100)}
        )
    else:
        r = requests.get(
            f"{BASE}/app.bsky.feed.getFeed",
            params={"feed": uri, "limit": min(limit, 100)}
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
