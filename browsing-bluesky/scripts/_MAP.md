# scripts/
*Files: 3*

## Files

### __init__.py
> Imports: `.bsky`
- *No top-level symbols*

### bsky.py
> Imports: `os, requests, subprocess, json, re`...
- **is_authenticated** (f) `()` :122
- **get_authenticated_user** (f) `()` :132
- **clear_session** (f) `()` :144
- **get_profile** (f) `(handle: str)` :150
- **get_user_posts** (f) `(handle: str, limit: int = 20)` :178
- **search_posts** (f) `(
    query: str,
    author: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 25
)` :198
- **get_feed_posts** (f) `(feed_uri: str, limit: int = 20)` :240
- **sample_firehose** (f) `(duration: int = 10, filter: Optional[str] = None)` :282
- **get_thread** (f) `(post_uri_or_url: str, depth: int = 6, parent_height: int = 80)` :314
- **get_quotes** (f) `(post_uri_or_url: str, limit: int = 25)` :335
- **get_likes** (f) `(post_uri_or_url: str, limit: int = 50)` :354
- **get_reposts** (f) `(post_uri_or_url: str, limit: int = 50)` :373
- **get_followers** (f) `(handle: str, limit: int = 50)` :392
- **get_following** (f) `(handle: str, limit: int = 50)` :411
- **search_users** (f) `(query: str, limit: int = 25)` :430

### zeitgeist-sample.js
- *No top-level symbols*

