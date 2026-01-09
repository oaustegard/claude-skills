# scripts/
*Files: 3*

## Files

### __init__.py
> Imports: `.bsky`
- *No top-level symbols*

### bsky.py
> Imports: `requests, subprocess, json, re, typing`...
- **get_profile** (f) `(handle: str)`
- **get_user_posts** (f) `(handle: str, limit: int = 20)`
- **search_posts** (f) `(
    query: str,
    author: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 25
)`
- **get_feed_posts** (f) `(feed_uri: str, limit: int = 20)`
- **sample_firehose** (f) `(duration: int = 10, filter: Optional[str] = None)`
- **get_thread** (f) `(post_uri_or_url: str, depth: int = 6, parent_height: int = 80)`
- **get_quotes** (f) `(post_uri_or_url: str, limit: int = 25)`
- **get_likes** (f) `(post_uri_or_url: str, limit: int = 50)`
- **get_reposts** (f) `(post_uri_or_url: str, limit: int = 50)`
- **get_followers** (f) `(handle: str, limit: int = 50)`
- **get_following** (f) `(handle: str, limit: int = 50)`
- **search_users** (f) `(query: str, limit: int = 25)`

### zeitgeist-sample.js
- *No top-level symbols*

