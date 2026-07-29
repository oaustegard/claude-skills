"""Bluesky browsing module - API, firehose, and account analysis."""

from .scripts.bsky import (
    analyze_account,
    analyze_accounts,
    clear_session,
    extract_keywords,
    extract_post_text,
    get_all_followers,
    # Account analysis (from categorizing-bsky-accounts)
    get_all_following,
    get_authenticated_user,
    get_feed_posts,
    get_followers,
    get_following,
    get_likes,
    get_profile,
    get_quotes,
    get_reposts,
    get_thread,
    # Trending
    get_trending,
    get_trending_topics,
    get_user_posts,
    # Authentication utilities
    is_authenticated,
    sample_firehose,
    # Core browsing
    search_posts,
    search_users,
)

__all__ = [
    # Core browsing
    "search_posts",
    "get_user_posts",
    "get_profile",
    "get_feed_posts",
    "sample_firehose",
    "get_thread",
    "get_quotes",
    "get_likes",
    "get_reposts",
    "get_followers",
    "get_following",
    "search_users",
    # Trending
    "get_trending",
    "get_trending_topics",
    # Account analysis
    "get_all_following",
    "get_all_followers",
    "extract_post_text",
    "extract_keywords",
    "analyze_account",
    "analyze_accounts",
    # Authentication utilities
    "is_authenticated",
    "get_authenticated_user",
    "clear_session"
]
