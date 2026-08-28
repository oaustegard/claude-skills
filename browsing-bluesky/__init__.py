"""Bluesky browsing module - API, firehose, and account analysis."""

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
    "authenticated_identity",
    "get_authenticated_user",
    "clear_session"
]

# This directory's name has a hyphen, so the package is reachable only through
# importlib — and pytest's Package collector execs this file with no parent
# package at all when it collects tests/, where the relative import below
# raises. Falling back to a by-path load keeps both routes working; the other
# skills that carry tests have no root __init__.py and never hit this.
try:
    from .scripts.bsky import (
        analyze_account,
        analyze_accounts,
        clear_session,
        extract_keywords,
        extract_post_text,
        get_all_followers,
        # Account analysis (from categorizing-bsky-accounts)
        get_all_following,
        authenticated_identity,
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
except ImportError:  # pragma: no cover - exercised by pytest's collector
    import importlib.util as _importlib_util
    from pathlib import Path as _Path

    _spec = _importlib_util.spec_from_file_location(
        "_browsing_bluesky_bsky", _Path(__file__).parent / "scripts" / "bsky.py")
    _bsky = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_bsky)
    globals().update({_n: getattr(_bsky, _n) for _n in __all__})
