#!/usr/bin/env python3
"""
Generate progressive disclosure indexes for GitHub repositories.

Usage:
    python github_index.py owner/repo -o index.md
    python github_index.py owner/repo1 owner/repo2 -o combined.md
    python github_index.py owner/repo --include-patterns "docs/**" "blog/**"
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional


@dataclass
class FileInfo:
    path: str
    title: Optional[str] = None
    description: Optional[str] = None
    category: str = "Other"


@dataclass  
class RepoInfo:
    owner: str
    repo: str
    branch: str
    url: str
    description: str
    files: list[FileInfo] = field(default_factory=list)


SKIP_DIRS = frozenset({
    'node_modules', '.git', '__pycache__', '.venv', 'venv',
    'dist', 'build', '_site', '.next', 'target', '.cache'
})

CONTENT_EXTENSIONS = frozenset({'.md', '.qmd', '.ipynb', '.rst', '.mdx'})


def api_request(url: str, token: Optional[str] = None, timeout: int = 30) -> dict:
    """Make GitHub API request with error handling."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError(f"Rate limited or forbidden: {url}")
        elif e.code == 404:
            raise RuntimeError(f"Not found: {url}")
        raise
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def get_repo_info(owner: str, repo: str, token: Optional[str] = None) -> tuple[str, str]:
    """Get default branch and description."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    data = api_request(url, token)
    return data.get("default_branch", "main"), data.get("description", "")


def get_repo_tree(owner: str, repo: str, branch: str, token: Optional[str] = None) -> list[str]:
    """Fetch all file paths from repository."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    data = api_request(url, token, timeout=60)
    return [f["path"] for f in data.get("tree", []) if f["type"] == "blob"]


def should_include(path: str, include: list[str], exclude: list[str]) -> bool:
    """Check if path passes include/exclude filters."""
    parts = Path(path).parts
    # Skip common noise directories
    if any(part in SKIP_DIRS for part in parts):
        return False
    # Skip underscore-prefixed files (typically partials/includes)
    if Path(path).name.startswith('_'):
        return False
    for pattern in exclude:
        if fnmatch(path, pattern):
            return False
    if include:
        return any(fnmatch(path, pattern) for pattern in include)
    return True


def is_content_file(path: str) -> bool:
    """Check if file is indexable content."""
    return Path(path).suffix.lower() in CONTENT_EXTENSIONS


def fetch_file(owner: str, repo: str, path: str, branch: str, 
               token: Optional[str] = None) -> Optional[str]:
    """Fetch file content via Contents API."""
    encoded = urllib.parse.quote(path, safe='/')
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded}?ref={branch}"
    
    try:
        data = api_request(url, token)
        content = base64.b64decode(data["content"])
        return content.decode("utf-8", errors="replace")
    except Exception:
        return None


def extract_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter for title/description."""
    if not content.startswith("---"):
        return {}
    
    match = re.search(r'\n---\s*\n', content[3:])
    if not match:
        return {}
    
    yaml_text = content[3:match.start() + 3]
    result = {}
    
    for line in yaml_text.split('\n'):
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip().lower()
            value = value.strip().strip('"\'')
            # Handle multi-line or HTML in descriptions
            value = re.sub(r'<[^>]+>', '', value)  # Strip HTML
            if key in ('title', 'description') and value:
                result[key] = value
    
    return result


def extract_notebook_title(content: str) -> dict:
    """Extract title from Jupyter notebook first cell."""
    try:
        nb = json.loads(content)
        cells = nb.get("cells", [])
        if cells and cells[0].get("cell_type") == "markdown":
            source = "".join(cells[0].get("source", []))
            match = re.search(r'^#\s+(.+)$', source, re.MULTILINE)
            if match:
                return {"title": match.group(1).strip()}
    except (json.JSONDecodeError, KeyError):
        pass
    return {}


def infer_category(path: str) -> str:
    """Derive category from path structure."""
    parts = Path(path).parts
    
    patterns = [
        (['blog', 'posts'], "Blog Posts"),
        (['docs', 'documentation'], "Documentation"),
        (['guides', 'tutorials'], "Guides"),
        (['api'], "API Reference"),
        (['examples'], "Examples"),
    ]
    
    for keywords, category in patterns:
        if any(k in parts for k in keywords):
            return category
    
    if 'notes' in parts:
        try:
            idx = parts.index('notes')
            if len(parts) > idx + 1:
                sub = parts[idx + 1].replace('_', ' ').replace('-', ' ').title()
                return f"Notes: {sub}"
        except ValueError:
            pass
        return "Notes"
    
    if len(parts) > 1:
        return parts[0].replace('_', ' ').replace('-', ' ').title()
    
    return "Other"


def description_from_path(path: str) -> str:
    """Generate fallback description from filename."""
    stem = Path(path).stem
    if stem == "index":
        parent = Path(path).parent.name
        return parent.replace('_', ' ').replace('-', ' ').title() if parent != '.' else "Index"
    return stem.replace('_', ' ').replace('-', ' ')


def process_repo(owner: str, repo: str, token: Optional[str] = None,
                 include: list[str] = None, exclude: list[str] = None,
                 max_files: int = 200, skip_fetch: bool = False) -> RepoInfo:
    """Process repository and extract file metadata."""
    include = include or []
    exclude = exclude or []
    
    print(f"Processing {owner}/{repo}...", file=sys.stderr)
    
    branch, desc = get_repo_info(owner, repo, token)
    all_paths = get_repo_tree(owner, repo, branch, token)
    
    content_paths = [
        p for p in all_paths
        if is_content_file(p) and should_include(p, include, exclude)
    ]
    
    print(f"  Found {len(content_paths)} content files", file=sys.stderr)
    
    if len(content_paths) > max_files:
        print(f"  Limiting to {max_files} files", file=sys.stderr)
        content_paths = content_paths[:max_files]
    
    files: list[FileInfo] = []
    
    if skip_fetch:
        for path in content_paths:
            files.append(FileInfo(
                path=path,
                description=description_from_path(path),
                category=infer_category(path)
            ))
    else:
        def process_file(path: str) -> FileInfo:
            content = fetch_file(owner, repo, path, branch, token)
            meta = {}
            if content:
                if path.endswith('.ipynb'):
                    meta = extract_notebook_title(content)
                else:
                    meta = extract_frontmatter(content)
            
            desc = meta.get('description') or meta.get('title') or description_from_path(path)
            return FileInfo(
                path=path,
                title=meta.get('title'),
                description=desc,
                category=infer_category(path)
            )
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_file, p): p for p in content_paths}
            done = 0
            for future in as_completed(futures):
                files.append(future.result())
                done += 1
                if done % 50 == 0:
                    print(f"  Processed {done}/{len(content_paths)}", file=sys.stderr)
    
    return RepoInfo(
        owner=owner,
        repo=repo,
        branch=branch,
        url=f"https://github.com/{owner}/{repo}",
        description=desc,
        files=files
    )


def generate_index(repos: list[RepoInfo]) -> str:
    """Generate markdown index content."""
    lines = []
    
    # Header
    if len(repos) == 1:
        r = repos[0]
        lines.append(f"# {r.repo} - Content Index\n")
        lines.append(f"**Repository:** {r.url}  ")
        lines.append(f"**Branch:** `{r.branch}`")
        if r.description:
            lines.append(f"\n*{r.description}*")
    else:
        lines.append("# Combined Repository Index\n")
        for r in repos:
            lines.append(f"- [{r.owner}/{r.repo}]({r.url})")
    
    lines.append("\n## Retrieval Method\n")
    lines.append("Fetch source files via GitHub Contents API:")
    lines.append("```bash")
    lines.append('curl -s "https://api.github.com/repos/OWNER/REPO/contents/PATH?ref=BRANCH" \\')
    lines.append('  -H "Accept: application/vnd.github+json" | \\')
    lines.append('  python3 -c "import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)[\'content\']).decode())"')
    lines.append("```\n")
    lines.append("---\n")
    
    # Content sections
    for r in repos:
        if len(repos) > 1:
            lines.append(f"## {r.owner}/{r.repo}\n")
        
        by_category: dict[str, list[FileInfo]] = {}
        for f in r.files:
            by_category.setdefault(f.category, []).append(f)
        
        for category in sorted(by_category.keys()):
            cat_files = sorted(by_category[category], key=lambda x: x.path)
            lines.append(f"### {category}\n")
            lines.append("| Description | Path |")
            lines.append("|-------------|------|")
            
            for f in cat_files:
                desc = f.description or "—"
                if len(desc) > 100:
                    desc = desc[:97] + "..."
                # Escape pipes in description
                desc = desc.replace("|", "\\|")
                lines.append(f"| {desc} | `{f.path}` |")
            
            lines.append("")
    
    lines.append("---\n")
    lines.append("*Generated by building-github-index*")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate progressive disclosure index for GitHub repos"
    )
    parser.add_argument("repos", nargs="+", help="Repositories (owner/repo format)")
    parser.add_argument("-o", "--output", default="github_index.md", help="Output file")
    parser.add_argument("--token", help="GitHub PAT (or set GITHUB_TOKEN env)")
    parser.add_argument("--include-patterns", nargs="*", default=[], help="Include glob patterns")
    parser.add_argument("--exclude-patterns", nargs="*", default=[], help="Exclude glob patterns")
    parser.add_argument("--max-files", type=int, default=200, help="Max files per repo")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip content fetching")
    
    args = parser.parse_args()
    token = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT")
    
    repos_data = []
    for spec in args.repos:
        if "/" not in spec:
            print(f"Error: Invalid format '{spec}', expected owner/repo", file=sys.stderr)
            continue
        
        owner, repo = spec.split("/", 1)
        try:
            data = process_repo(
                owner, repo, token,
                args.include_patterns, args.exclude_patterns,
                args.max_files, args.skip_fetch
            )
            repos_data.append(data)
        except Exception as e:
            print(f"Error processing {spec}: {e}", file=sys.stderr)
    
    if not repos_data:
        print("No repositories processed successfully", file=sys.stderr)
        sys.exit(1)
    
    index_content = generate_index(repos_data)
    Path(args.output).write_text(index_content)
    print(f"Index written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
