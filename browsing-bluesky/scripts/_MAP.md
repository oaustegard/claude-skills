# scripts/
*Files: 3*

## Files

### __init__.py
> Imports: `.bsky`
- *No top-level symbols*

### bsky.py
> Imports: `requests, subprocess, json, re, typing`...
- **get_profile** (f) `(handle: str)` :14
- **get_user_posts** (f) `(handle: str, limit: int = 20)` :38
- **search_posts** (f) `(
    query: str,
    author: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 25
)` :57
- **get_feed_posts** (f) `(feed_uri: str, limit: int = 20)` :98
- **sample_firehose** (f) `(duration: int = 10, filter: Optional[str] = None)` :135
- **get_thread** (f) `(post_uri_or_url: str, depth: int = 6, parent_height: int = 80)` :167
- **get_quotes** (f) `(post_uri_or_url: str, limit: int = 25)` :188
- **get_likes** (f) `(post_uri_or_url: str, limit: int = 50)` :207
- **get_reposts** (f) `(post_uri_or_url: str, limit: int = 50)` :226
- **get_followers** (f) `(handle: str, limit: int = 50)` :245
- **get_following** (f) `(handle: str, limit: int = 50)` :264
- **search_users** (f) `(query: str, limit: int = 25)` :283

### zeitgeist-sample.js
- *No top-level symbols*

