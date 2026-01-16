# scripts/
*Files: 1*

## Files

### github_index.py
> Imports: `argparse, base64, json, os, re`...
- **api_request** (f) `(url: str, token: Optional[str] = None, timeout: int = 30)` :52
- **get_repo_info** (f) `(owner: str, repo: str, token: Optional[str] = None)` :72
- **get_repo_tree** (f) `(owner: str, repo: str, branch: str, token: Optional[str] = None)` :79
- **should_include** (f) `(path: str, include: list[str], exclude: list[str])` :86
- **is_content_file** (f) `(path: str)` :103
- **fetch_file** (f) `(owner: str, repo: str, path: str, branch: str, 
               token: Optional[str] = None)` :108
- **extract_frontmatter** (f) `(content: str)` :122
- **extract_notebook_title** (f) `(content: str)` :147
- **infer_category** (f) `(path: str)` :162
- **description_from_path** (f) `(path: str)` :194
- **process_repo** (f) `(owner: str, repo: str, token: Optional[str] = None,
                 include: list[str] = None, exclude: list[str] = None,
                 max_files: int = 200, skip_fetch: bool = False)` :203
- **generate_index** (f) `(repos: list[RepoInfo])` :272
- **main** (f) `()` :329

