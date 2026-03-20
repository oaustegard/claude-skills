"""World tools for perch sessions.

Maps Anthropic tool-use calls to browsing-bluesky functions and web fetching.
"""

import sys
import os
import importlib
import json
import requests

import anthropic

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
                    "description": "Max posts to return (default 10, max 100).",
                    "default": 10,
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
                    "description": "Max results (default 15, max 100).",
                    "default": 15,
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
        "name": "create_discussion",
        "description": (
            "Create a GitHub Discussion in the claude-skills repo. Use the Flight Log "
            "category for fly exploration findings. Title should be descriptive of the "
            "topic explored. Body should be the synthesis in markdown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Discussion title — descriptive of the exploration topic",
                },
                "body": {
                    "type": "string",
                    "description": (
                        "Discussion body in markdown — the synthesis, key findings, "
                        "connections made, and threads worth pursuing"
                    ),
                },
                "category_id": {
                    "type": "string",
                    "description": (
                        "Discussion category ID. Defaults to Flight Log "
                        "(DIC_kwDOQEB8Es4C31s9)"
                    ),
                    "default": "DIC_kwDOQEB8Es4C31s9",
                },
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "discussion_comments",
        "description": (
            "Check recent GitHub Discussion comments in the Flight Log category. "
            "Returns Oskar's comments on fly exploration discussions — use during "
            "dispatch or fly to incorporate feedback into thread selection."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "since_days": {
                    "type": "integer",
                    "description": "Look back this many days for comments (default 7).",
                    "default": 7,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max discussions to check (default 10).",
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
            "reader as fallback for blocked sites. Low-level tool — prefer "
            "deep_read for articles (it analyzes in isolation and keeps context lean)."
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
    {
        "name": "deep_read",
        "description": (
            "Read and analyze a URL in an isolated sub-agent. Fetches the full "
            "page, analyzes it with Haiku in a separate context, stores the full "
            "analysis in memory, and returns only a 2-3 sentence summary. Use "
            "this instead of fetch_url for articles and papers — it keeps your "
            "conversation context lean while capturing all the detail in memory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch and analyze.",
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Why you're reading this — e.g., 'checking if this paper "
                        "relates to selective consolidation in agent memory'. "
                        "Helps the sub-agent focus its analysis."
                    ),
                },
            },
            "required": ["url"],
        },
    },
]


# -- Known feed URIs --

KNOWN_FEEDS = {
    "ai_list": "at://did:plc:r2whjvupgfw55mllpksnombn/app.bsky.graph.list/3lankcdrlip2f",
    "paperskygest": "at://did:plc:uaadt6f5bbda6cycbmatcm3z/app.bsky.feed.generator/preprintdigest",
}


# -- Tool executors --

def execute_bsky_feed(input: dict) -> str:
    """Read posts from a Bluesky feed or list."""
    feed = input["feed"]
    limit = min(input.get("limit", 10), 100)

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
        limit=min(input.get("limit", 15), 100),
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


def _create_discussion(input: dict) -> str:
    """Create a GitHub Discussion in the Flight Log category."""
    import urllib.request

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return "Error: No GitHub token available"

    repo_id = "R_kgDOQEB8Eg"
    category_id = input.get("category_id", "DIC_kwDOQEB8Es4C31s9")
    title = input.get("title", "Untitled fly exploration")
    body = input.get("body", "")

    # Ensure Oskar gets notified (github-actions[bot] doesn't trigger notifications)
    if "cc @oaustegard" not in body.lower():
        body = body.rstrip() + "\n\ncc @oaustegard"

    mutation = """mutation($input: CreateDiscussionInput!) {
      createDiscussion(input: $input) {
        discussion { id number url }
      }
    }"""

    variables = {
        "input": {
            "repositoryId": repo_id,
            "categoryId": category_id,
            "title": title,
            "body": body,
        }
    }

    payload = json.dumps({"query": mutation, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        if "errors" in data:
            return f"GraphQL errors: {data['errors']}"
        disc = data["data"]["createDiscussion"]["discussion"]
        return f"Discussion #{disc['number']} created: {disc['url']}"
    except Exception as e:
        return f"Failed to create discussion: {e}"


def execute_discussion_comments(input: dict) -> str:
    """Check recent comments on Flight Log discussions from Oskar."""
    import urllib.request
    from datetime import datetime, timedelta, timezone

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return "Error: No GitHub token available"

    since_days = input.get("since_days", 7)
    limit = min(input.get("limit", 10), 20)

    # Compute cutoff date
    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()

    # GraphQL query: recent Flight Log discussions with comments
    query = """query($owner: String!, $repo: String!, $limit: Int!) {
      repository(owner: $owner, name: $repo) {
        discussions(
          first: $limit,
          categoryId: "DIC_kwDOQEB8Es4C31s9",
          orderBy: {field: UPDATED_AT, direction: DESC}
        ) {
          nodes {
            number
            title
            url
            updatedAt
            comments(first: 10) {
              nodes {
                author { login }
                body
                createdAt
              }
            }
          }
        }
      }
    }"""

    variables = {"owner": "oaustegard", "repo": "claude-skills", "limit": limit}
    payload = json.dumps({"query": query, "variables": variables}).encode()

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
    except Exception as e:
        return f"Failed to query discussions: {e}"

    if "errors" in data:
        return f"GraphQL errors: {data['errors']}"

    discussions = data.get("data", {}).get("repository", {}).get("discussions", {}).get("nodes", [])
    if not discussions:
        return "No recent Flight Log discussions found."

    # Filter to discussions with comments from Oskar (repo owner)
    oskar_login = "oaustegard"
    feedback = []

    for disc in discussions:
        comments = disc.get("comments", {}).get("nodes", [])
        oskar_comments = [
            c for c in comments
            if c.get("author", {}).get("login") == oskar_login
            and c.get("createdAt", "") >= cutoff
        ]
        if oskar_comments:
            for c in oskar_comments:
                feedback.append({
                    "discussion_number": disc["number"],
                    "discussion_title": disc["title"],
                    "discussion_url": disc["url"],
                    "comment": c["body"][:500],
                    "commented_at": c["createdAt"],
                })

    if not feedback:
        return f"No comments from Oskar on Flight Log discussions in the last {since_days} days."

    lines = []
    for f in feedback:
        lines.append(
            f"Discussion #{f['discussion_number']}: {f['discussion_title']}\n"
            f"  URL: {f['discussion_url']}\n"
            f"  Comment ({f['commented_at']}): {f['comment']}"
        )

    return f"{len(feedback)} comment(s) from Oskar:\n\n" + "\n\n".join(lines)


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


# -- Deep read sub-agent --

_DEEP_READ_SYSTEM = """\
You are a document analysis agent. You read web pages and extract structured information.

Given a fetched web page and optional context about why it's being read, produce a JSON response with:
- "summary": 2-3 sentence summary of key claims and significance (what matters and why)
- "full": Detailed analysis (500-1500 words). Cover: key claims, evidence quality, \
connections to broader topics, notable quotes, and anything surprising or novel.
- "tags": List of 3-7 lowercase topic tags for memory retrieval (e.g., ["agent-memory", "consolidation", "2026-research"])

Respond with ONLY valid JSON, no markdown fencing."""


def _fetch_full(url: str) -> str:
    """Fetch full page content without truncation. Direct + Jina fallback."""
    # Try direct fetch
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; Muninn/1.0)"
        })
        if resp.status_code == 200 and len(resp.text.strip()) > 100:
            return resp.text.strip()
    except requests.RequestException:
        pass

    # Fallback to Jina reader for full content
    try:
        jina_url = f"https://r.jina.ai/{url}"
        resp = requests.get(jina_url, timeout=30, headers={
            "Accept": "text/plain",
        })
        if resp.status_code == 200:
            return resp.text.strip()
    except requests.RequestException:
        pass

    return ""


def _analyze_with_subagent(content: str, url: str, context: str) -> dict:
    """Run isolated Haiku call to analyze page content. Returns dict with summary/full/tags."""
    # Cap content to avoid blowing up the sub-agent context
    max_content = 50_000
    if len(content) > max_content:
        content = content[:max_content] + "\n\n[... content truncated for analysis]"

    user_msg = f"URL: {url}\n"
    if context:
        user_msg += f"Context: {context}\n"
    user_msg += f"\n--- PAGE CONTENT ---\n{content}"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=_DEEP_READ_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text

    # Parse JSON response
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown fencing
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group())
            except json.JSONDecodeError:
                result = {}
        else:
            result = {}

    return {
        "summary": result.get("summary", "Analysis failed — could not parse sub-agent response."),
        "full": result.get("full", raw[:2000]),
        "tags": result.get("tags", []),
    }


def execute_deep_read(input: dict) -> str:
    """Fetch URL, analyze in isolated sub-agent, store to memory, return brief summary."""
    url = input["url"]
    context = input.get("context", "")

    # 1. Fetch full content
    content = _fetch_full(url)
    if not content:
        return f"Failed to fetch {url} (both direct and Jina fallback failed)."

    # 2. Sub-agent analysis (isolated Haiku call)
    analysis = _analyze_with_subagent(content, url, context)

    # 3. Store full analysis in memory
    try:
        from remembering.scripts import remember as mem_remember
        mem_id = mem_remember(
            what=f"DEEP READ: {url}\n\n{analysis['full']}",
            type="world",
            tags=["deep-read", "perch"] + [t for t in analysis.get("tags", []) if isinstance(t, str)],
        )
    except Exception as e:
        mem_id = f"store-failed-{e}"

    # 4. Return only the brief summary
    short_id = str(mem_id)[:8] if mem_id else "no-id"
    return f"[{short_id}] {analysis['summary']}"


# -- Executor dispatch --

WORLD_EXECUTORS = {
    "bsky_feed": execute_bsky_feed,
    "bsky_search": execute_bsky_search,
    "bsky_trending": execute_bsky_trending,
    "create_discussion": _create_discussion,
    "discussion_comments": execute_discussion_comments,
    "fetch_url": execute_fetch_url,
    "deep_read": execute_deep_read,
}
