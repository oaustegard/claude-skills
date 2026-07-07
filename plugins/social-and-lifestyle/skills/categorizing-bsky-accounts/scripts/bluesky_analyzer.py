#!/usr/bin/env python3
"""
BlueSky Account Analyzer
Fetches Bluesky account data and extracts keywords for Claude to categorize.

Usage:
  python scripts/bluesky_analyzer.py --following austegard.com --stopwords ai
  python scripts/bluesky_analyzer.py --followers handle.bsky.social
  python scripts/bluesky_analyzer.py --handles "h1.bsky.social,h2.bsky.social"
"""

import json
import requests
import sys
import argparse
from typing import List, Dict, Tuple, Optional
import tempfile
import subprocess
import os

API_BASE = "https://public.api.bsky.app/xrpc"

# ============================================================================
# API Functions
# ============================================================================

def get_following(actor: str, limit: int = 100, cursor: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
    """Fetch list of accounts followed by the actor with pagination."""
    url = f"{API_BASE}/app.bsky.graph.getFollows"
    params = {"actor": actor, "limit": min(limit, 100)}
    if cursor:
        params["cursor"] = cursor

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("follows", []), data.get("cursor")
    except requests.RequestException as e:
        print(f"Error fetching following list: {e}", file=sys.stderr)
        return [], None

def get_followers(actor: str, limit: int = 100, cursor: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
    """Fetch list of accounts following the actor with pagination."""
    url = f"{API_BASE}/app.bsky.graph.getFollowers"
    params = {"actor": actor, "limit": min(limit, 100)}
    if cursor:
        params["cursor"] = cursor

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("followers", []), data.get("cursor")
    except requests.RequestException as e:
        print(f"Error fetching followers list: {e}", file=sys.stderr)
        return [], None

def get_all_following(actor: str, max_limit: int = 100) -> List[Dict]:
    """Fetch following with cursor pagination."""
    all_accounts = []
    cursor = None

    while len(all_accounts) < max_limit:
        batch_size = min(100, max_limit - len(all_accounts))
        accounts, cursor = get_following(actor, limit=batch_size, cursor=cursor)

        if not accounts:
            break

        all_accounts.extend(accounts)

        if not cursor or len(all_accounts) >= max_limit:
            break

    return all_accounts[:max_limit]

def get_all_followers(actor: str, max_limit: int = 100) -> List[Dict]:
    """Fetch followers with cursor pagination."""
    all_accounts = []
    cursor = None

    while len(all_accounts) < max_limit:
        batch_size = min(100, max_limit - len(all_accounts))
        accounts, cursor = get_followers(actor, limit=batch_size, cursor=cursor)

        if not accounts:
            break

        all_accounts.extend(accounts)

        if not cursor or len(all_accounts) >= max_limit:
            break

    return all_accounts[:max_limit]

def get_author_feed(actor: str, limit: int = 20) -> List[Dict]:
    """Fetch recent posts from an account."""
    url = f"{API_BASE}/app.bsky.feed.getAuthorFeed"
    params = {"actor": actor, "limit": limit, "filter": "posts_no_replies"}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("feed", [])
    except requests.RequestException as e:
        return []

def extract_text_from_posts(posts: List[Dict]) -> str:
    """Extract and concatenate text content from posts."""
    texts = []
    for item in posts:
        post = item.get("post", {})
        record = post.get("record", {})
        text = record.get("text", "")
        if text:
            texts.append(text)
    return " ".join(texts)

# ============================================================================
# Keyword Extraction
# ============================================================================

def extract_keywords(text: str, top_n: int = 10, language: str = "en") -> List[str]:
    """Extract keywords using extracting-keywords skill's YAKE venv.

    Args:
        text: Text to extract keywords from
        top_n: Number of keywords to return
        language: Stopwords to use - "en", "ai", or "ls"

    Returns:
        List of keyword strings (without scores)
    """
    if not text or len(text) < 100:
        return []

    try:
        # Path to extracting-keywords venv and assets
        venv_python = "/home/claude/yake-venv/bin/python"

        # Try multiple possible paths for extracting-keywords assets
        possible_paths = [
            "/mnt/skills/user/extracting-keywords/assets",
            "/home/user/claude-skills/extracting-keywords/assets",
            os.path.join(os.path.dirname(__file__), "..", "..", "extracting-keywords", "assets")
        ]

        assets_path = None
        for path in possible_paths:
            if os.path.exists(os.path.join(path, "stopwords_ai.txt")):
                assets_path = path
                break

        if not assets_path:
            raise FileNotFoundError("Cannot find extracting-keywords assets directory")

        stopwords_path = {
            "ai": os.path.join(assets_path, "stopwords_ai.txt"),
            "ls": os.path.join(assets_path, "stopwords_ls.txt")
        }

        # Write text to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp.write(text)
            tmp_path = tmp.name

        # Build extraction script - output just keywords (no scores)
        if language in stopwords_path:
            stopwords_config = f"""
with open('{stopwords_path[language]}', 'r') as f:
    stopwords_config = {{'stopwords': set(line.strip().lower() for line in f)}}
"""
        else:
            stopwords_config = f"stopwords_config = {{'lan': '{language}'}}"

        extraction_script = f"""
import yake

with open('{tmp_path}', 'r') as f:
    text = f.read()

{stopwords_config}

kw_extractor = yake.KeywordExtractor(n=3, dedupLim=0.9, top={top_n}, **stopwords_config)
keywords = kw_extractor.extract_keywords(text)

for kw, score in keywords:
    print(kw)
"""

        # Execute via extracting-keywords venv
        result = subprocess.run(
            [venv_python, "-c", extraction_script],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Clean up temp file
        os.unlink(tmp_path)

        if result.returncode == 0:
            keywords = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            return keywords
        else:
            print(f"Keyword extraction error: {result.stderr}", file=sys.stderr)
            return []

    except Exception as e:
        print(f"Keyword extraction error: {e}", file=sys.stderr)
        return []

# ============================================================================
# Analysis Functions
# ============================================================================

def should_exclude(bio: str, keywords: List[str], exclude_patterns: List[str]) -> bool:
    """Check if account should be excluded based on patterns."""
    if not exclude_patterns:
        return False

    text = f"{bio} {' '.join(keywords)}"
    text_lower = text.lower()

    for pattern in exclude_patterns:
        if pattern.lower() in text_lower:
            return True

    return False

def analyze_account(handle: str, display_name: str, description: str,
                   post_limit: int = 20, language: str = "en") -> Dict:
    """Analyze a single account: fetch posts and extract keywords."""
    posts = get_author_feed(handle, limit=post_limit)
    text = extract_text_from_posts(posts)
    keywords = extract_keywords(text, language=language)

    return {
        "handle": handle,
        "display_name": display_name,
        "bio": description or "(no bio)",
        "keywords": keywords,
        "post_count": len(posts)
    }

# ============================================================================
# Input Processing
# ============================================================================

def get_accounts_from_handles(handles_str: str) -> List[Dict]:
    """Parse comma-separated handles and return account list."""
    handles = [h.strip() for h in handles_str.split(',') if h.strip()]
    accounts = []

    for handle in handles:
        accounts.append({
            "handle": handle,
            "displayName": "",
            "description": ""
        })

    return accounts

def get_accounts_from_file(file_path: str) -> List[Dict]:
    """Read handles from file (one per line)."""
    accounts = []

    try:
        with open(file_path, 'r') as f:
            for line in f:
                handle = line.strip()
                if handle and not handle.startswith('#'):
                    accounts.append({
                        "handle": handle,
                        "displayName": "",
                        "description": ""
                    })
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)

    return accounts

# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Fetch BlueSky account data and extract keywords for Claude to categorize',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python %(prog)s --following austegard.com --stopwords ai
  python %(prog)s --followers handle.bsky.social
  python %(prog)s --handles "user1.bsky.social,user2.bsky.social"
        """
    )

    # Input modes (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--handles', help='Comma-separated list of handles')
    input_group.add_argument('--following', help='Analyze accounts followed by this handle')
    input_group.add_argument('--followers', help='Analyze accounts following this handle')
    input_group.add_argument('--file', help='Read handles from file (one per line)')

    # Analysis options
    parser.add_argument('--accounts', type=int, default=100,
                       help='Number of accounts to analyze (default: 100, max: 100)')
    parser.add_argument('--posts', type=int, default=20,
                       help='Number of posts per account (default: 20)')
    parser.add_argument('--exclude', help='Skip accounts with these keywords (comma-separated)')
    parser.add_argument('--stopwords', choices=['en', 'ai', 'ls'], default='en',
                       help='Stopwords to use: en=English, ai=AI/ML domain, ls=Life Sciences domain (default: en)')

    args = parser.parse_args()

    # Validate limits
    args.accounts = min(args.accounts, 100)
    args.posts = min(args.posts, 100)

    # Parse exclude patterns
    exclude_patterns = [p.strip() for p in args.exclude.split(',')] if args.exclude else []

    # Get accounts based on input mode
    print("Fetching accounts...", file=sys.stderr)
    if args.handles:
        accounts = get_accounts_from_handles(args.handles)
    elif args.following:
        accounts = get_all_following(args.following, max_limit=args.accounts)
    elif args.followers:
        accounts = get_all_followers(args.followers, max_limit=args.accounts)
    elif args.file:
        accounts = get_accounts_from_file(args.file)

    print(f"Found {len(accounts)} accounts\n", file=sys.stderr)

    if not accounts:
        print("No accounts to analyze", file=sys.stderr)
        return

    # Analyze accounts
    print(f"Analyzing accounts...\n", file=sys.stderr)
    results = []

    for i, account in enumerate(accounts, 1):
        handle = account.get("handle", "")
        print(f"  [{i}/{len(accounts)}] {handle}...", end="", flush=True, file=sys.stderr)

        analysis = analyze_account(
            handle,
            account.get("displayName", ""),
            account.get("description", ""),
            post_limit=args.posts,
            language=args.stopwords
        )

        print(f" {analysis['post_count']} posts, {len(analysis['keywords'])} keywords", file=sys.stderr)

        # Apply exclusion filter
        if should_exclude(analysis['bio'], analysis['keywords'], exclude_patterns):
            print(f"    (excluded)", file=sys.stderr)
            continue

        results.append(analysis)

    print(f"\n{'='*80}\n", file=sys.stderr)
    print(f"Analyzed {len(results)} accounts\n", file=sys.stderr)

    if not results:
        print("No accounts matched filters", file=sys.stderr)
        return

    # Output simple text format for Claude to process
    for account in results:
        name = account['display_name'] or account['handle'].split('.')[0]
        handle = account['handle']
        bio = account['bio']
        keywords = ', '.join(account['keywords']) if account['keywords'] else '(insufficient content)'

        print(f"@{handle} ({name})")
        print(bio)
        print(f"Keywords: {keywords}")
        print()

if __name__ == "__main__":
    main()
