# browsing-bluesky

Comprehensive Bluesky browsing via public APIs and real-time firehose.

## Features

- **Search posts** - Advanced search with filters (query syntax matching bsky.app)
- **User monitoring** - Fetch profiles and recent posts
- **Feed/list reading** - Read from custom feeds and curated lists
- **Firehose sampling** - Real-time trending topic detection

## Network Requirements

This skill requires the following URLs to be whitelisted in your environment:

### API Access
- `https://api.bsky.app` - Bluesky public API (search, profiles, feeds)
  - Used by: `search_posts()`, `get_user_posts()`, `get_profile()`, `get_feed_posts()`

### Firehose Access
- `wss://jetstream1.us-east.bsky.network` - Bluesky Jetstream firehose WebSocket
  - Used by: `sample_firehose()`

### Important Notes

- **Do NOT use** `public.api.bsky.app` - This subdomain returns 403 errors from some environments
- **Always use** `api.bsky.app` instead
- No authentication required for public read operations

## Dependencies

### Python
- `requests` - For HTTP API calls

### Node.js (for firehose sampling only)
- `ws` - WebSocket client
- `https-proxy-agent` - Proxy support

Install Node.js dependencies once per session:
```bash
cd /home/claude && npm install ws https-proxy-agent
```

## Installation

Add the skill directory to your Python path:

```python
import sys
sys.path.insert(0, '/path/to/browsing-bluesky')
from browsing_bluesky import search_posts, get_user_posts, get_profile, get_feed_posts, sample_firehose
```

## Usage Examples

### Search Posts
```python
# Basic search
posts = search_posts("event sourcing", limit=10)

# With filters
posts = search_posts("MCP", author="austegard.com", since="2025-01-01", limit=20)

# Query syntax (like bsky.app advanced search)
posts = search_posts('from:acairns.co.uk "event sourcing" lang:en')
```

### Monitor a User
```python
# Get profile
profile = get_profile("austegard.com")
print(f"{profile['display_name']}: {profile['followers']} followers")

# Get recent posts
posts = get_user_posts("austegard.com", limit=20)
```

### Read Feeds and Lists
```python
# From URL
posts = get_feed_posts("https://bsky.app/profile/austegard.com/lists/3lankcdrlip2f")

# From AT-URI
posts = get_feed_posts("at://did:plc:xxx/app.bsky.graph.list/xyz")
```

### Sample Trending Topics
```python
# Sample for 30 seconds
data = sample_firehose(duration=30)
print(f"Top words: {data['topWords'][:10]}")
print(f"Trending phrases: {data['topPhrases'][:5]}")
print(f"Entities: {data['entities'][:5]}")

# Filter for specific term
data = sample_firehose(duration=20, filter="python")
print(f"Found {data['stats']['totalPosts']} posts about 'python'")
```

## Return Data Format

All API functions return structured dictionaries:

**Post objects:**
```python
{
    "uri": "at://...",
    "text": "Post content",
    "created_at": "2025-01-01T00:00:00.000Z",
    "author_handle": "user.bsky.social",
    "author_name": "Display Name",
    "likes": 42,
    "reposts": 10,
    "replies": 5,
    "url": "https://bsky.app/profile/user.bsky.social/post/..."
}
```

**Profile objects:**
```python
{
    "handle": "user.bsky.social",
    "display_name": "Display Name",
    "description": "Bio text",
    "followers": 100,
    "following": 50,
    "posts": 200,
    "did": "did:plc:..."
}
```

**Firehose sample data:**
```python
{
    "window": {"startTime": "...", "endTime": "...", "durationSeconds": 30},
    "stats": {"totalReceived": 1000, "totalPosts": 500, "postsPerSecond": 16.7},
    "topWords": [["word", count], ...],
    "topPhrases": [["phrase", count], ...],
    "entities": [["Named Entity", count], ...],
    "samplePosts": [{"text": "...", "altTexts": [...], "hasImages": true}, ...]
}
```

## Troubleshooting

### 403 Errors from API
- Ensure you're using `api.bsky.app` not `public.api.bsky.app`
- Verify `api.bsky.app` is whitelisted in your environment

### Firehose Sampling Fails
- Check Node.js dependencies are installed: `npm list ws https-proxy-agent`
- Verify `jetstream1.us-east.bsky.network` WebSocket access is allowed
- If behind a proxy, ensure `https_proxy` environment variable is set

### Module Import Errors
- Directory name has hyphens (`browsing-bluesky`) but module uses underscores (`browsing_bluesky`)
- Use `importlib.util.spec_from_file_location()` if standard import fails

## Related Skills

This skill consolidates and replaces:
- `sampling-bluesky-zeitgeist` (deprecated) - Firehose sampling now built-in

## Version

0.5.0
