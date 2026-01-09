# scripts/
*Files: 1*

## Files

### bluesky_analyzer.py
> Imports: `json, requests, sys, argparse, typing`...
- **get_following** (f) `(actor: str, limit: int = 100, cursor: Optional[str] = None)`
- **get_followers** (f) `(actor: str, limit: int = 100, cursor: Optional[str] = None)`
- **get_all_following** (f) `(actor: str, max_limit: int = 100)`
- **get_all_followers** (f) `(actor: str, max_limit: int = 100)`
- **get_author_feed** (f) `(actor: str, limit: int = 20)`
- **extract_text_from_posts** (f) `(posts: List[Dict])`
- **extract_keywords** (f) `(text: str, top_n: int = 10, language: str = "en")`
- **should_exclude** (f) `(bio: str, keywords: List[str], exclude_patterns: List[str])`
- **analyze_account** (f) `(handle: str, display_name: str, description: str,
                   post_limit: int = 20, language: str = "en")`
- **get_accounts_from_handles** (f) `(handles_str: str)`
- **get_accounts_from_file** (f) `(file_path: str)`
- **main** (f) `()`

