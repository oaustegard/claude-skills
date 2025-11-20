#!/usr/bin/env python3
"""
BlueSky Account Analyzer - Enhanced Version
Analyzes and categorizes Bluesky accounts by topic.

Features:
- Multiple input modes (handles, following, followers, file)
- Pagination support for large lists
- Custom category definitions
- Multiple output formats (grouped, detailed, JSON, CSV, markdown)
- Filtering and exclusion patterns

Usage examples:
  python bluesky_analyzer.py --handles "h1.bsky.social,h2.bsky.social"
  python bluesky_analyzer.py --following austegard.com --accounts 50
  python bluesky_analyzer.py --followers austegard.com --accounts 20
  python bluesky_analyzer.py --file accounts.txt --format csv
"""

import json
import requests
import sys
import csv
from collections import defaultdict
from typing import List, Dict, Tuple, Set, Optional
import argparse
from pathlib import Path

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
# Analysis Functions
# ============================================================================

def extract_keywords(text: str, top_n: int = 15) -> List[Tuple[str, float]]:
    """Extract keywords from text using YAKE."""
    if not text or len(text) < 100:
        return []
    
    try:
        import yake
        kw_extractor = yake.KeywordExtractor(
            lan="en",
            n=3,
            dedupLim=0.9,
            top=top_n
        )
        return kw_extractor.extract_keywords(text)
    except Exception as e:
        print(f"Keyword extraction error: {e}", file=sys.stderr)
        return []

def load_categories(categories_file: Optional[str] = None) -> Dict:
    """Load category definitions from JSON or use defaults."""
    default_categories = {
        'AI/ML': {
            'keywords': ['ai', 'ml', 'machine learning', 'model', 'llm', 'gemini', 'claude',
                        'data', 'learning', 'neural', 'deep learning', 'nlp'],
            'weight': 1.0
        },
        'Software Dev': {
            'keywords': ['python', 'code', 'github', 'dev', 'programming', 'api',
                        'mcp', 'prefect', 'atproto', 'opensource', 'software'],
            'weight': 1.0
        },
        'Philosophy': {
            'keywords': ['philosophy', 'discourse', 'mind', 'consciousness', 'epistemic',
                        'metaphysics', 'ethics'],
            'weight': 1.0
        },
        'Music': {
            'keywords': ['music', 'streaming', 'audio', 'song', 'album', 'band', 'artist'],
            'weight': 1.0
        },
        'Law/Policy': {
            'keywords': ['law', 'copyright', 'legal', 'policy', 'regulation', 'court',
                        'attorney', 'professor'],
            'weight': 1.0
        },
        'Engineering': {
            'keywords': ['engineering', 'infrastructure', 'system', 'architecture',
                        'cloud', 'devops'],
            'weight': 1.0
        },
        'Science': {
            'keywords': ['research', 'paper', 'study', 'science', 'phd', 'university',
                        'academic'],
            'weight': 1.0
        },
    }
    
    if categories_file:
        try:
            with open(categories_file, 'r') as f:
                custom_categories = json.load(f)
                # Validate structure
                for cat, data in custom_categories.items():
                    if 'keywords' not in data:
                        data['keywords'] = []
                    if 'weight' not in data:
                        data['weight'] = 1.0
                return custom_categories
        except Exception as e:
            print(f"Error loading categories file: {e}, using defaults", file=sys.stderr)
    
    return default_categories

def analyze_account(handle: str, display_name: str, description: str,
                   post_limit: int = 20, verbose: bool = True) -> Dict:
    """Analyze a single account: fetch posts and extract keywords."""
    if verbose:
        print(f"  {handle}…", end="", flush=True)
    
    posts = get_author_feed(handle, limit=post_limit)
    text = extract_text_from_posts(posts)
    keywords = extract_keywords(text)
    
    if verbose:
        print(f" {len(posts)} posts, {len(keywords)} keywords")
    
    return {
        "handle": handle,
        "display_name": display_name,
        "description": description,
        "post_count": len(posts),
        "text_length": len(text),
        "keywords": keywords
    }

def categorize_by_domain(account: Dict, categories: Dict, show_confidence: bool = False) -> Tuple[str, float]:
    """Categorize account by domain based on keywords and bio."""
    keywords = account.get('keywords', [])
    description = account.get('description', '').lower()
    
    kw_text = " ".join([kw for kw, _ in keywords[:10]]).lower()
    combined = kw_text + " " + description
    
    scores = defaultdict(float)
    for domain, data in categories.items():
        patterns = data.get('keywords', [])
        weight = data.get('weight', 1.0)
        for pattern in patterns:
            if pattern in combined:
                scores[domain] += weight
    
    if scores:
        best_category = max(scores.items(), key=lambda x: x[1])
        category, score = best_category
        # Calculate confidence based on score distribution
        total_score = sum(scores.values())
        confidence = score / total_score if total_score > 0 else 0.0
        return category, confidence
    
    return 'Other', 0.0

def should_exclude(account: Dict, exclude_patterns: List[str]) -> bool:
    """Check if account should be excluded based on patterns."""
    if not exclude_patterns:
        return False
    
    text = f"{account.get('description', '')} {' '.join([kw for kw, _ in account.get('keywords', [])])}"
    text_lower = text.lower()
    
    for pattern in exclude_patterns:
        if pattern.lower() in text_lower:
            return True
    
    return False

def should_include(account: Dict, filter_categories: List[str], categories: Dict) -> bool:
    """Check if account matches filter categories."""
    if not filter_categories:
        return True
    
    category, _ = categorize_by_domain(account, categories)
    return category in filter_categories

# ============================================================================
# Display Functions
# ============================================================================

def format_account_detailed(account: Dict, category: str, confidence: float, show_confidence: bool) -> str:
    """Format detailed account info."""
    lines = []
    
    name = account['display_name'] or account['handle'].split('.')[0]
    handle = account['handle']
    
    lines.append(f"\n{name} (@{handle})")
    if show_confidence:
        lines.append(f"Category: {category} (confidence: {confidence:.2f})")
    else:
        lines.append(f"Category: {category}")
    lines.append(f"Posts analyzed: {account['post_count']}")
    
    if account['description']:
        desc = account['description'][:100]
        if len(account['description']) > 100:
            desc += "..."
        lines.append(f"Bio: {desc}")
    
    if account['keywords']:
        lines.append("Top Keywords:")
        for kw, score in account['keywords'][:8]:
            lines.append(f"  • {kw:30} ({score:.4f})")
    else:
        lines.append("Keywords: (insufficient content)")
    
    return "\n".join(lines)

def format_account_grouped(account: Dict, show_confidence: bool, confidence: float) -> str:
    """Format concise account info for grouped display."""
    lines = []
    
    name = account['display_name'] or account['handle'].split('.')[0]
    handle = account['handle']
    
    conf_str = f" (conf: {confidence:.2f})" if show_confidence else ""
    lines.append(f"**{name}** (@{handle}){conf_str}")
    
    if account['description']:
        desc = account['description'][:80]
        if len(account['description']) > 80:
            desc += "..."
        lines.append(f"  {desc}")
    
    if account['keywords'] and len(account['keywords']) >= 3:
        top_kws = [kw for kw, _ in account['keywords'][:5]]
        lines.append(f"  Topics: {', '.join(top_kws)}")
    
    return "\n".join(lines)

def display_grouped_results(results: List[Tuple[Dict, str, float]], show_confidence: bool, categories: Dict):
    """Display accounts grouped by topic."""
    domains = defaultdict(list)
    for account, category, confidence in results:
        domains[category].append((account, confidence))
    
    print("\n" + "="*80)
    print("ACCOUNTS GROUPED BY TOPIC")
    print("="*80)
    
    for domain in sorted(domains.keys()):
        accounts_data = domains[domain]
        print(f"\n## {domain} ({len(accounts_data)} accounts)\n")
        
        for account, confidence in accounts_data:
            print(format_account_grouped(account, show_confidence, confidence))
            print()

def display_detailed_results(results: List[Tuple[Dict, str, float]], show_confidence: bool, categories: Dict):
    """Display detailed analysis for each account."""
    print("\n" + "="*80)
    print("DETAILED ANALYSIS")
    print("="*80)
    
    for account, category, confidence in results:
        print(format_account_detailed(account, category, confidence, show_confidence))

def export_json(results: List[Tuple[Dict, str, float]], output_path: str):
    """Export results as JSON."""
    output = {
        "accounts": []
    }
    
    for account, category, confidence in results:
        output["accounts"].append({
            "handle": account["handle"],
            "display_name": account["display_name"],
            "description": account["description"],
            "category": category,
            "confidence": round(confidence, 3),
            "post_count": account["post_count"],
            "keywords": [{"keyword": kw, "score": round(score, 4)} for kw, score in account["keywords"]]
        })
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to {output_path}")

def export_csv(results: List[Tuple[Dict, str, float]], output_path: str):
    """Export results as CSV."""
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['handle', 'display_name', 'category', 'confidence', 'top_keywords', 'bio'])
        
        for account, category, confidence in results:
            top_kws = ', '.join([kw for kw, _ in account['keywords'][:5]])
            writer.writerow([
                account['handle'],
                account['display_name'],
                category,
                round(confidence, 3),
                top_kws,
                account['description'][:100] if account['description'] else ''
            ])
    
    print(f"\nResults saved to {output_path}")

def export_markdown(results: List[Tuple[Dict, str, float]], output_path: str, show_confidence: bool):
    """Export results as Markdown."""
    domains = defaultdict(list)
    for account, category, confidence in results:
        domains[category].append((account, confidence))
    
    with open(output_path, 'w') as f:
        f.write("# Bluesky Account Analysis\n\n")
        
        for domain in sorted(domains.keys()):
            accounts_data = domains[domain]
            f.write(f"## {domain} ({len(accounts_data)} accounts)\n\n")
            
            for account, confidence in accounts_data:
                name = account['display_name'] or account['handle'].split('.')[0]
                handle = account['handle']
                
                conf_str = f" (confidence: {confidence:.2f})" if show_confidence else ""
                f.write(f"### {name} (@{handle}){conf_str}\n\n")
                
                if account['description']:
                    f.write(f"{account['description']}\n\n")
                
                if account['keywords']:
                    top_kws = ', '.join([kw for kw, _ in account['keywords'][:5]])
                    f.write(f"**Topics:** {top_kws}\n\n")
    
    print(f"\nResults saved to {output_path}")

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
        description='Analyze BlueSky accounts and categorize by topic',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python %(prog)s --handles "user1.bsky.social,user2.bsky.social"
  python %(prog)s --following austegard.com --accounts 50
  python %(prog)s --followers austegard.com --accounts 20
  python %(prog)s --file accounts.txt --format csv
        """
    )
    
    # Input modes (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--handles', help='Comma-separated list of handles')
    input_group.add_argument('--following', help='Analyze accounts followed by this handle')
    input_group.add_argument('--followers', help='Analyze accounts following this handle')
    input_group.add_argument('--file', help='Read handles from file (one per line)')
    
    # Analysis options
    parser.add_argument('--accounts', type=int, default=10,
                       help='Number of accounts to analyze (default: 10, max: 100)')
    parser.add_argument('--posts', type=int, default=20,
                       help='Number of posts per account (default: 20)')
    parser.add_argument('--filter', help='Only analyze accounts in these categories (comma-separated)')
    parser.add_argument('--exclude', help='Skip accounts with these keywords (comma-separated)')
    parser.add_argument('--categories', help='Custom category definitions (JSON file)')
    
    # Output options
    parser.add_argument('--format', choices=['grouped', 'detailed', 'json', 'csv', 'markdown'],
                       default='grouped', help='Output format (default: grouped)')
    parser.add_argument('--output', default='/home/claude/bluesky_analysis',
                       help='Output file path (extension added based on format)')
    parser.add_argument('--confidence', action='store_true',
                       help='Show categorization confidence scores')
    
    args = parser.parse_args()
    
    # Validate limits
    args.accounts = min(args.accounts, 100)
    args.posts = min(args.posts, 100)
    
    # Load categories
    categories = load_categories(args.categories)
    
    # Parse filter and exclude patterns
    filter_categories = [c.strip() for c in args.filter.split(',')] if args.filter else []
    exclude_patterns = [p.strip() for p in args.exclude.split(',')] if args.exclude else []
    
    # Get accounts based on input mode
    print("Fetching accounts...")
    if args.handles:
        accounts = get_accounts_from_handles(args.handles)
    elif args.following:
        accounts = get_all_following(args.following, max_limit=args.accounts)
    elif args.followers:
        accounts = get_all_followers(args.followers, max_limit=args.accounts)
    elif args.file:
        accounts = get_accounts_from_file(args.file)
    
    print(f"Found {len(accounts)} accounts\n")
    
    if not accounts:
        print("No accounts to analyze")
        return
    
    # Analyze accounts
    print("Analyzing accounts...")
    results = []
    processed = 0
    
    for account in accounts:
        analysis = analyze_account(
            account.get("handle", ""),
            account.get("displayName", ""),
            account.get("description", ""),
            post_limit=args.posts
        )
        
        # Apply exclusion filter
        if should_exclude(analysis, exclude_patterns):
            continue
        
        # Get category
        category, confidence = categorize_by_domain(analysis, categories, args.confidence)
        
        # Apply category filter
        if filter_categories and category not in filter_categories:
            continue
        
        results.append((analysis, category, confidence))
        processed += 1
    
    print(f"\nProcessed {processed} accounts")
    
    if not results:
        print("No accounts matched filters")
        return
    
    # Determine output file extension
    ext_map = {
        'json': '.json',
        'csv': '.csv',
        'markdown': '.md',
        'grouped': '.txt',
        'detailed': '.txt'
    }
    output_path = args.output + ext_map.get(args.format, '.txt')
    
    # Display or export results
    if args.format == 'json':
        export_json(results, output_path)
    elif args.format == 'csv':
        export_csv(results, output_path)
    elif args.format == 'markdown':
        export_markdown(results, output_path, args.confidence)
    elif args.format == 'detailed':
        display_detailed_results(results, args.confidence, categories)
    else:  # grouped
        display_grouped_results(results, args.confidence, categories)

if __name__ == "__main__":
    main()
