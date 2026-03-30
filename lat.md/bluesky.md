# Bluesky

Three skills interact with the Bluesky/ATProto ecosystem: browsing-bluesky provides comprehensive API access, categorizing-bsky-accounts classifies accounts by topic, and extracting-keywords powers the analysis via YAKE.

## API Surface

[[browsing-bluesky/scripts/bsky.py#search_posts]] queries the Bluesky search API with filters for author, date range, and language. [[browsing-bluesky/scripts/bsky.py#get_user_posts]] fetches a user's timeline. [[browsing-bluesky/scripts/bsky.py#get_thread]] retrieves full conversation threads with configurable depth.

Social graph traversal uses [[browsing-bluesky/scripts/bsky.py#get_followers]] and [[browsing-bluesky/scripts/bsky.py#get_following]] for paginated access, with [[browsing-bluesky/scripts/bsky.py#get_all_followers]] and [[browsing-bluesky/scripts/bsky.py#get_all_following]] handling cursor-based pagination to exhaustion.

[[browsing-bluesky/scripts/bsky.py#get_feed_posts]] reads custom algorithm feeds. [[browsing-bluesky/scripts/bsky.py#get_trending]] and [[browsing-bluesky/scripts/bsky.py#get_trending_topics]] surface network-wide trends.

## Firehose Sampling

[[browsing-bluesky/scripts/bsky.py#sample_firehose]] connects to the Bluesky relay WebSocket for real-time post sampling with optional text filtering. This absorbed the deprecated sampling-bluesky-zeitgeist skill's functionality.

## Engagement Analysis

[[browsing-bluesky/scripts/bsky.py#get_likes]], [[browsing-bluesky/scripts/bsky.py#get_reposts]], and [[browsing-bluesky/scripts/bsky.py#get_quotes]] retrieve engagement data for individual posts. Combined with [[browsing-bluesky/scripts/bsky.py#get_profile]] for account metadata.

## Account Analysis

[[browsing-bluesky/scripts/bsky.py#analyze_account]] computes a topic profile for a single account by fetching posts, extracting keywords, and combining with bio text. [[browsing-bluesky/scripts/bsky.py#analyze_accounts]] scales this to lists of handles or entire follower/following graphs with exclusion pattern support.

The keyword extraction uses [[browsing-bluesky/scripts/bsky.py#extract_keywords]] which wraps the YAKE algorithm. [[browsing-bluesky/scripts/bsky.py#extract_post_text]] preprocesses post data for keyword extraction.

## Standalone Categorizer

[[categorizing-bsky-accounts/scripts/bluesky_analyzer.py#analyze_account]] is an earlier, standalone version of account analysis. [[categorizing-bsky-accounts/scripts/bluesky_analyzer.py#extract_keywords]] implements its own YAKE wrapper with domain-specific stopwords. [[categorizing-bsky-accounts/scripts/bluesky_analyzer.py#should_exclude]] filters accounts matching exclusion patterns.

The redundancy between [[categorizing-bsky-accounts/scripts/bluesky_analyzer.py#analyze_account]] and [[browsing-bluesky/scripts/bsky.py#analyze_account]] is a known consolidation opportunity — browsing-bluesky absorbed this functionality but the standalone skill was not removed.

## Authentication

[[browsing-bluesky/scripts/bsky.py#is_authenticated]] and [[browsing-bluesky/scripts/bsky.py#get_authenticated_user]] manage session state. [[browsing-bluesky/scripts/bsky.py#clear_session]] resets credentials. Authentication uses app passwords from environment variables.
