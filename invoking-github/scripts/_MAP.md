# scripts/
*Files: 2*

## Files

### __init__.py
> Imports: `.github_client`
- *No top-level symbols*

### github_client.py
> Imports: `json, sys, base64, pathlib, typing`...
- **GitHubAPIError** (C) :17
  - **__init__** (m) `(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None)` :26
- **get_github_token** (f) `()` :33
- **read_file** (f) `(repo: str, path: str, branch: str = "main")` :198
- **commit_file** (f) `(
    repo: str,
    path: str,
    content: str,
    branch: str,
    message: str,
    create_branch_from: Optional[str] = None
)` :233
- **commit_files** (f) `(
    repo: str,
    files: List[Dict[str, str]],
    branch: str,
    message: str,
    create_branch_from: Optional[str] = None
)` :311
- **create_pull_request** (f) `(
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str = ""
)` :417

