"""World tools for perch sessions.

Maps Anthropic tool-use calls to browsing-bluesky functions and web fetching.
"""

import sys
import os
import importlib
import json
import requests

# Ensure the repo root is on sys.path
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# browsing-bluesky uses a hyphen, so we need importlib
_bsky = importlib.import_module("browsing-bluesky")


# -- Tool definitions (Anthropic Messages API format) --

WORLD_TOOLS = [
    {
        "name": "bsky_feed",
        "description": (
            "Read posts from a curated Bluesky feed or list. Accepts feed names "
            "(ai_list, paperskygest) or full URLs/AT-URIs. Returns recent posts "
            "with text, links, and engagement counts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feed": {
                    "type": "string",
                    "description": (
                        "Feed identifier: a known name (ai_list, paperskygest), "
                        "a bsky.app URL, or an AT-URI."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max posts to return (default 20, max 100).",
                    "default": 20,
                },
            },
            "required": ["feed"],
        },
    },
    {
        "name": "bsky_search",
        "description": (
            "Search Bluesky posts by query. Supports advanced syntax: "
            "from:user, mentions:user, #hashtag, domain:site, lang:xx, "
            "since:YYYY-MM-DD, until:YYYY-MM-DD."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (supports advanced Bluesky search syntax).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 25, max 100).",
                    "default": 25,
                },
                "since": {
                    "type": "string",
                    "description": "Filter posts after this date (YYYY-MM-DD).",
                },
                "until": {
                    "type": "string",
                    "description": "Filter posts before this date (YYYY-MM-DD).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "bsky_trending",
        "description": (
            "Get trending topics on Bluesky. Returns topics with display names, "
            "post counts, and categories. Use for awareness of current discourse."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max topics to return (default 10, max 25).",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch content from a URL and return as clean text. Uses Jina AI "
            "reader as fallback for blocked sites. Use to follow links from "
            "Bluesky posts to full articles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Truncate response to this many characters (default 8000).",
                    "default": 8000,
                },
            },
            "required": ["url"],
        },
    },
]


# -- Known feed URIs --

KNOWN_FEEDS = {
    "ai_list": "https://bsky.app/profile/austegard.com/lists/3lankcdrlip2f",
    "paperskygest": "https://bsky.app/profile/paperskygest.bsky.social/feed/paperskygest",
}


# -- Tool executors --

def execute_bsky_feed(input: dict) -> str:
    """Read posts from a Bluesky feed or list."""
    feed = input["feed"]
    limit = min(input.get("limit", 20), 100)

    # Resolve known feed names
    feed_uri = KNOWN_FEEDS.get(feed, feed)

    posts = _bsky.get_feed_posts(feed_uri, limit=limit)
    if not posts:
        return "No posts found in feed."

    lines = []
    for p in posts:
        text = p.get("text", "").replace("\n", " ")[:200]
        links = p.get("links", [])
        link_str = f" | links: {', '.join(links[:3])}" if links else ""
        lines.append(
            f"@{p.get('author_handle', '?')} ({p.get('likes', 0)}L {p.get('reposts', 0)}R)\n"
            f"  {text}{link_str}"
        )
    return f"{len(posts)} posts from {feed}:\n\n" + "\n\n".join(lines)


def execute_bsky_search(input: dict) -> str:
    """Search Bluesky posts."""
    posts = _bsky.search_posts(
        query=input["query"],
        limit=min(input.get("limit", 25), 100),
        since=input.get("since"),
        until=input.get("until"),
    )
    if not posts:
        return "No posts found."

    lines = []
    for p in posts:
        text = p.get("text", "").replace("\n", " ")[:200]
        links = p.get("links", [])
        link_str = f" | links: {', '.join(links[:3])}" if links else ""
        lines.append(
            f"@{p.get('author_handle', '?')} ({p.get('likes', 0)}L {p.get('reposts', 0)}R)\n"
            f"  {text}{link_str}"
        )
    return f"{len(posts)} results for '{input['query']}':\n\n" + "\n\n".join(lines)


def execute_bsky_trending(input: dict) -> str:
    """Get trending topics on Bluesky."""
    limit = min(input.get("limit", 10), 25)
    trends = _bsky.get_trending(limit=limit)
    if not trends:
        return "No trending topics found."

    lines = []
    for t in trends:
        name = t.get("display_name") or t.get("topic", "?")
        count = t.get("post_count", "?")
        category = t.get("category", "")
        cat_str = f" [{category}]" if category else ""
        lines.append(f"- {name}: {count} posts{cat_str}")
    return f"{len(trends)} trending topics:\n\n" + "\n".join(lines)


def execute_fetch_url(input: dict) -> str:
    """Fetch URL content, with Jina fallback for blocked sites."""
    url = input["url"]
    max_chars = input.get("max_chars", 8000)

    # Try direct fetch first
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; Muninn/1.0)"
        })
        if resp.status_code == 200 and len(resp.text.strip()) > 100:
            return _truncate(resp.text.strip(), max_chars)
    except requests.RequestException:
        pass

    # Fallback to Jina reader
    try:
        jina_url = f"https://r.jina.ai/{url}"
        resp = requests.get(jina_url, timeout=20, headers={
            "Accept": "text/plain",
        })
        if resp.status_code == 200:
            return _truncate(resp.text.strip(), max_chars)
    except requests.RequestException:
        pass

    return f"Failed to fetch {url} (both direct and Jina fallback failed)."


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text with indicator."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n[... truncated at {max_chars} chars]"


# -- Executor dispatch --

WORLD_EXECUTORS = {
    "bsky_feed": execute_bsky_feed,
    "bsky_search": execute_bsky_search,
    "bsky_trending": execute_bsky_trending,
    "fetch_url": execute_fetch_url,
}
