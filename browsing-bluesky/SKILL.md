---
name: browsing-bluesky
description: Browse Bluesky content via API and firehose - search posts, fetch user activity, sample trending topics, read feeds and lists. Use for Bluesky research, user monitoring, trend analysis, feed reading, firehose sampling.
metadata:
  version: 0.1.0
---

# Browsing Bluesky

Access Bluesky content through public APIs and real-time firehose.

## Implementation

Add skill directory to path and import:

```python
import sys
sys.path.insert(0, '/path/to/skills/browsing-bluesky')  # or use .claude/skills symlink path
from browsing_bluesky import search_posts, get_user_posts, get_profile, get_feed_posts, sample_firehose
```

## Research Workflows

### Investigate a Topic

Use `search_posts()` with query syntax matching bsky.app advanced search:
- Basic terms: `event sourcing`
- Exact phrases: `"event sourcing"`
- User filter: `from:acairns.co.uk` or use `author=` param
- Date filter: `since:2025-01-01` or use `since=` param
- Hashtags, mentions, domain links: `#python mentions:user domain:github.com`

Combine query syntax with function params for complex searches.

### Monitor a User

1. Fetch profile with `get_profile(handle)` for context (bio, follower count, post count)
2. Get recent posts with `get_user_posts(handle, limit=N)`
3. For topic-specific user content, use `search_posts(query, author=handle)`

### Sample Trending Topics

**Prerequisites**: Install Node.js dependencies once per session:
```bash
cd /home/claude && npm install ws https-proxy-agent 2>/dev/null
```

**Usage**:
```python
data = sample_firehose(duration=30)  # Sample for 30 seconds
data = sample_firehose(duration=20, filter="python")  # Filter for specific term
```

Returns: `topWords`, `topPhrases`, `entities`, `samplePosts`, `stats`

Use for real-time zeitgeist, trending topic detection, or filtered stream analysis.

### Read Feeds and Lists

`get_feed_posts()` accepts:
- List URLs: `https://bsky.app/profile/austegard.com/lists/3lankcdrlip2f`
- Feed URLs: `https://bsky.app/profile/did:plc:xxx/feed/feedname`
- AT-URIs: `at://did:plc:xxx/app.bsky.graph.list/xyz`

The function extracts the AT-URI from URLs automatically.

## API Endpoint Notes

- **Base**: `https://api.bsky.app/xrpc/` (NOT `public.api.bsky.app` which returns 403)
- **Firehose**: `wss://jetstream1.us-east.bsky.network/subscribe`
- **No authentication** required for public reads
- **Rate limits** exist but are generous for read operations

## Return Format

All API functions return structured dicts with:
- `uri`: AT protocol identifier
- `text`: Post content
- `created_at`: ISO timestamp
- `author_handle`: User handle
- `author_name`: Display name
- `likes`, `reposts`, `replies`: Engagement counts
- `url`: Direct link to post on bsky.app

Profile function returns: `handle`, `display_name`, `description`, `followers`, `following`, `posts`, `did`
