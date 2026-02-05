# scripts/
*Files: 2*

## Files

### github_index.py
> Imports: `argparse, base64, json, os, re`...
- **api_request** (f) `(url: str, token: Optional[str] = None, timeout: int = 30)` :57
- **get_repo_info** (f) `(owner: str, repo: str, token: Optional[str] = None)` :72
- **get_repo_tree** (f) `(owner: str, repo: str, branch: str, token: Optional[str] = None)` :77
- **should_include** (f) `(path: str, include: list[str], exclude: list[str])` :82
- **fetch_file** (f) `(owner: str, repo: str, path: str, branch: str, 
               token: Optional[str] = None)` :95
- **extract_frontmatter** (f) `(content: str)` :106
- **extract_headings** (f) `(content: str)` :124
- **extract_notebook_title** (f) `(content: str)` :143
- **extract_code_symbols** (f) `(content: str, lang: str)` :156
- **infer_category** (f) `(path: str)` :194
- **description_from_path** (f) `(path: str)` :212
- **process_repo** (f) `(owner: str, repo: str, token: Optional[str] = None,
                 include: list[str] = None, exclude: list[str] = None,
                 max_files: int = 200, skip_fetch: bool = False,
                 code_symbols: bool = False)` :219
- **generate_index** (f) `(repos: list[RepoInfo])` :295
- **main** (f) `()` :341

### pk_index.py
> Imports: `json, os, sys, tarfile, tempfile`...
- **fetch_tarball** (f) `(owner: str, repo: str, ref: str = 'main')` :31
- **extract_md_topics** (f) `(content: str)` :37
- **extract_py_symbols** (f) `(content: bytes, parser)` :50
- **extract_js_symbols** (f) `(content: bytes, parser)` :67
- **process_repo** (f) `(owner: str, repo: str, ref: str = 'main', output: str = None)` :100
- **generate_pk_output** (f) `(owner: str, repo: str, ref: str, entries: list, output_path: str)` :169

