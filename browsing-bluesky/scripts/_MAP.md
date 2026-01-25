# scripts/
*Files: 3*

## Files

### __init__.py
> Imports: `.bsky`
- *No top-level symbols*

### bsky.py
> Imports: `os, requests, subprocess, json, re`...
- **is_authenticated** (f) `()` :137
- **get_authenticated_user** (f) `()` :147
- **clear_session** (f) `()` :159
- **get_profile** (f) `(handle: str)` :165
- **get_user_posts** (f) `(handle: str, limit: int = 20)` :194
- **search_posts** (f) `(
    query: str,
    author: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 25
)` :215
- **get_feed_posts** (f) `(feed_uri: str, limit: int = 20)` :258
- **sample_firehose** (f) `(duration: int = 10, filter: Optional[str] = None)` :300
- **get_thread** (f) `(post_uri_or_url: str, depth: int = 6, parent_height: int = 80)` :332
- **get_quotes** (f) `(post_uri_or_url: str, limit: int = 25)` :353
- **get_likes** (f) `(post_uri_or_url: str, limit: int = 50)` :372
- **get_reposts** (f) `(post_uri_or_url: str, limit: int = 50)` :391
- **get_followers** (f) `(handle: str, limit: int = 50)` :410
- **get_following** (f) `(handle: str, limit: int = 50)` :429
- **search_users** (f) `(query: str, limit: int = 25)` :448

### zeitgeist-sample.js
- *No top-level symbols*

