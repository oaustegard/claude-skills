# scripts/
*Files: 1*

## Files

### bluesky_analyzer.py
> Imports: `json, requests, sys, argparse, typing`...
- **get_following** (f) `(actor: str, limit: int = 100, cursor: Optional[str] = None)` :27
- **get_followers** (f) `(actor: str, limit: int = 100, cursor: Optional[str] = None)` :43
- **get_all_following** (f) `(actor: str, max_limit: int = 100)` :59
- **get_all_followers** (f) `(actor: str, max_limit: int = 100)` :78
- **get_author_feed** (f) `(actor: str, limit: int = 20)` :97
- **extract_text_from_posts** (f) `(posts: List[Dict])` :109
- **extract_keywords** (f) `(text: str, top_n: int = 10, language: str = "en")` :124
- **should_exclude** (f) `(bio: str, keywords: List[str], exclude_patterns: List[str])` :218
- **analyze_account** (f) `(handle: str, display_name: str, description: str,
                   post_limit: int = 20, language: str = "en")` :232
- **get_accounts_from_handles** (f) `(handles_str: str)` :251
- **get_accounts_from_file** (f) `(file_path: str)` :265
- **main** (f) `()` :288

