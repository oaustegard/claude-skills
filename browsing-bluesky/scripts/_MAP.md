# scripts/
*Files: 3*

## Files

### __init__.py
> Imports: `.bsky`
- *No top-level symbols*

### bsky.py
> Imports: `os, requests, subprocess, json, re`...
- **is_authenticated** (f) `()` :138
- **get_authenticated_user** (f) `()` :148
- **clear_session** (f) `()` :160
- **get_profile** (f) `(handle: str)` :166
- **get_user_posts** (f) `(handle: str, limit: int = 20)` :195
- **search_posts** (f) `(
    query: str,
    author: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    lang: Optional[str] = None,
    limit: int = 25
)` :216
- **get_feed_posts** (f) `(feed_uri: str, limit: int = 20)` :259
- **sample_firehose** (f) `(duration: int = 10, filter: Optional[str] = None)` :301
- **get_thread** (f) `(post_uri_or_url: str, depth: int = 6, parent_height: int = 80)` :333
- **get_quotes** (f) `(post_uri_or_url: str, limit: int = 25)` :354
- **get_likes** (f) `(post_uri_or_url: str, limit: int = 50)` :373
- **get_reposts** (f) `(post_uri_or_url: str, limit: int = 50)` :392
- **get_followers** (f) `(handle: str, limit: int = 50)` :411
- **get_following** (f) `(handle: str, limit: int = 50)` :430
- **search_users** (f) `(query: str, limit: int = 25)` :449
- **get_all_following** (f) `(handle: str, limit: int = 100)` :471
- **get_all_followers** (f) `(handle: str, limit: int = 100)` :508
- **extract_post_text** (f) `(posts: List[Dict[str, Any]])` :545
- **extract_keywords** (f) `(
    text: str,
    top_n: int = 10,
    stopwords: str = "en"
)` :557
- **analyze_account** (f) `(
    handle: str,
    posts_limit: int = 20,
    stopwords: str = "en"
)` :648
- **analyze_accounts** (f) `(
    handles: Optional[List[str]] = None,
    following: Optional[str] = None,
    followers: Optional[str] = None,
    limit: int = 100,
    posts_per_account: int = 20,
    stopwords: str = "en",
    exclude_patterns: Optional[List[str]] = None
)` :686

### zeitgeist-sample.js
- *No top-level symbols*

