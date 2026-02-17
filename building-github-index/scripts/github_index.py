#!/usr/bin/env python3
"""
Generate progressive disclosure indexes for GitHub repositories.
v3: Downloads repo tarball (single request) instead of per-file API calls.

Usage:
    python github_index.py owner/repo -o index.md
    python github_index.py owner/repo --code-symbols  # Include code files
"""

import argparse
import json
import os
import re
import sys
import tarfile
import tempfile
import urllib.request
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
    'dist', 'build', '_site', '.next', 'target', '.cache',
    'test', 'tests', '.github', 'vendor', 'third_party'
})

CONTENT_EXTENSIONS = frozenset({'.md', '.qmd', '.ipynb', '.rst', '.mdx'})
CODE_EXTENSIONS = frozenset({'.py', '.js', '.ts', '.tsx', '.go', '.rs', '.c', '.h', '.java', '.rb'})

try:
    from tree_sitter_language_pack import get_parser
    TS_AVAILABLE = True
except ImportError:
    TS_AVAILABLE = False

def api_request(url: str, token: Optional[str] = None, timeout: int = 30) -> dict:
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

def get_repo_info(owner: str, repo: str, token: Optional[str] = None) -> tuple[str, str]:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    data = api_request(url, token)
    return data.get("default_branch", "main"), data.get("description", "")

def fetch_tarball(owner: str, repo: str, branch: str, token: Optional[str] = None) -> bytes:
    url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{branch}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return resp.read()

def should_include(path: str, include: list[str], exclude: list[str]) -> bool:
    parts = Path(path).parts
    if any(part in SKIP_DIRS for part in parts):
        return False
    if Path(path).name.startswith('_'):
        return False
    for pattern in exclude:
        if fnmatch(path, pattern):
            return False
    if include:
        return any(fnmatch(path, pattern) for pattern in include)
    return True

def extract_frontmatter(content: str) -> dict:
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
            value = re.sub(r'<[^>]+>', '', value)
            if key in ('title', 'description') and value:
                result[key] = value
    return result

def extract_headings(content: str) -> dict:
    if content.startswith("---"):
        match = re.search(r'\n---\s*\n', content[3:])
        if match:
            content = content[match.end() + 3:]
    headings = re.findall(r'^#{1,2}\s+(.+)$', content, re.MULTILINE)
    if not headings:
        return {}
    result = {'title': headings[0].strip()}
    if len(headings) > 1:
        topics = [h.strip().lower() for h in headings[:4]]
        result['description'] = ', '.join(topics)
    return result

def extract_notebook_title(content: str) -> dict:
    try:
        nb = json.loads(content)
        cells = nb.get("cells", [])
        if cells and cells[0].get("cell_type") == "markdown":
            source = "".join(cells[0].get("source", []))
            match = re.search(r'^#\s+(.+)$', source, re.MULTILINE)
            if match:
                return {"title": match.group(1).strip()}
    except:
        pass
    return {}

def extract_code_symbols(content: str, lang: str) -> dict:
    if not TS_AVAILABLE:
        return {}
    lang_map = {'py': 'python', 'js': 'javascript', 'ts': 'typescript', 
                'tsx': 'tsx', 'go': 'go', 'rs': 'rust', 'c': 'c', 'h': 'c'}
    if lang not in lang_map:
        return {}
    try:
        parser = get_parser(lang_map[lang])
        tree = parser.parse(content.encode())
        symbols = []
        def get_text(node):
            return content[node.start_byte:node.end_byte]
        for node in tree.root_node.children:
            if node.type in ('function_definition', 'class_definition'):
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = get_text(name_node)
                    if not name.startswith('_'):
                        symbols.append(name)
            elif node.type == 'export_statement':
                for child in node.children:
                    if child.type in ('function_declaration', 'class_declaration'):
                        name_node = child.child_by_field_name('name')
                        if name_node:
                            symbols.append(get_text(name_node))
        if symbols:
            return {'description': ', '.join(symbols[:6]) + (f' +{len(symbols)-6}' if len(symbols) > 6 else '')}
    except:
        pass
    return {}

def infer_category(path: str) -> str:
    parts = Path(path).parts
    patterns = [
        (['blog', 'posts'], "Blog Posts"),
        (['docs', 'documentation'], "Documentation"),
        (['guides', 'tutorials'], "Guides"),
        (['api'], "API Reference"),
        (['examples'], "Examples"),
        (['src', 'lib'], "Source"),
        (['apps'], "Applications"),
    ]
    for keywords, category in patterns:
        if any(k in parts for k in keywords):
            return category
    if len(parts) > 1:
        return parts[0].replace('_', ' ').replace('-', ' ').title()
    return "Other"

def description_from_path(path: str) -> str:
    stem = Path(path).stem
    if stem.lower() in ('index', 'readme'):
        parent = Path(path).parent.name
        return parent.replace('_', ' ').replace('-', ' ').title() if parent != '.' else stem
    return stem.replace('_', ' ').replace('-', ' ')

def process_repo(owner: str, repo: str, token: Optional[str] = None,
                 include: list[str] = None, exclude: list[str] = None,
                 max_files: int = 200, skip_fetch: bool = False,
                 code_symbols: bool = False) -> RepoInfo:
    include = include or []
    exclude = exclude or []
    
    print(f"Processing {owner}/{repo}...", file=sys.stderr)
    branch, desc = get_repo_info(owner, repo, token)
    
    print(f"  Downloading tarball ({branch})...", file=sys.stderr)
    tarball_data = fetch_tarball(owner, repo, branch, token)
    
    valid_ext = CONTENT_EXTENSIONS | CODE_EXTENSIONS if code_symbols else CONTENT_EXTENSIONS
    files: list[FileInfo] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tarpath = Path(tmpdir) / 'repo.tar.gz'
        tarpath.write_bytes(tarball_data)
        
        with tarfile.open(tarpath, 'r:gz') as tar:
            tar.extractall(tmpdir)
        
        extracted_dirs = [d for d in Path(tmpdir).iterdir() if d.is_dir()]
        repo_root = extracted_dirs[0]
        
        candidate_paths = []
        for filepath in repo_root.rglob('*'):
            if not filepath.is_file():
                continue
            if filepath.suffix.lower() not in valid_ext:
                continue
            rel_str = str(filepath.relative_to(repo_root))
            if should_include(rel_str, include, exclude):
                candidate_paths.append((rel_str, filepath))
        
        print(f"  Found {len(candidate_paths)} files", file=sys.stderr)
        if len(candidate_paths) > max_files:
            print(f"  Limiting to {max_files}", file=sys.stderr)
            candidate_paths = candidate_paths[:max_files]
        
        for rel_str, filepath in candidate_paths:
            if skip_fetch:
                files.append(FileInfo(
                    path=rel_str,
                    description=description_from_path(rel_str),
                    category=infer_category(rel_str)
                ))
                continue
            
            try:
                content = filepath.read_text(errors='replace')
            except Exception:
                continue
            
            suffix = filepath.suffix.lower()
            meta = {}
            
            if suffix == '.ipynb':
                meta = extract_notebook_title(content)
            elif suffix in CONTENT_EXTENSIONS:
                meta = extract_frontmatter(content)
                if not meta.get('description') and not meta.get('title'):
                    meta = extract_headings(content)
            elif suffix.lstrip('.') in ('py', 'js', 'ts', 'tsx', 'go', 'rs', 'c', 'h') and code_symbols:
                meta = extract_code_symbols(content, suffix.lstrip('.'))
            
            file_desc = meta.get('description') or meta.get('title') or description_from_path(rel_str)
            files.append(FileInfo(
                path=rel_str,
                title=meta.get('title'),
                description=file_desc,
                category=infer_category(rel_str)
            ))
    
    print(f"  Indexed {len(files)} files", file=sys.stderr)
    return RepoInfo(
        owner=owner, repo=repo, branch=branch,
        url=f"https://github.com/{owner}/{repo}",
        description=desc, files=files
    )

def generate_index(repos: list[RepoInfo]) -> str:
    lines = []
    
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
    lines.append("```bash")
    lines.append('curl -s "https://api.github.com/repos/OWNER/REPO/contents/PATH?ref=BRANCH" \\')
    lines.append('  -H "Accept: application/vnd.github+json" | \\')
    lines.append("  python3 -c \"import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode())\"")
    lines.append("```\n---\n")
    
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
                desc = desc.replace("|", "\\|")
                lines.append(f"| {desc} | `{f.path}` |")
            lines.append("")
    
    lines.append("---\n*Generated by building-github-index*")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="GitHub repo index generator v3")
    parser.add_argument("repos", nargs="+", help="owner/repo")
    parser.add_argument("-o", "--output", default="github_index.md")
    parser.add_argument("--token", help="GitHub PAT")
    parser.add_argument("--include-patterns", nargs="*", default=[])
    parser.add_argument("--exclude-patterns", nargs="*", default=[])
    parser.add_argument("--max-files", type=int, default=200)
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Skip content extraction (filename-only descriptions)")
    parser.add_argument("--code-symbols", action="store_true", 
                        help="Include code files and extract symbols (requires tree-sitter)")
    
    args = parser.parse_args()
    token = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT")
    
    repos_data = []
    for spec in args.repos:
        if "/" not in spec:
            print(f"Error: Invalid '{spec}'", file=sys.stderr)
            continue
        owner, repo = spec.split("/", 1)
        try:
            data = process_repo(owner, repo, token, args.include_patterns, 
                              args.exclude_patterns, args.max_files, 
                              args.skip_fetch, args.code_symbols)
            repos_data.append(data)
        except Exception as e:
            print(f"Error: {spec}: {e}", file=sys.stderr)
    
    if not repos_data:
        sys.exit(1)
    
    Path(args.output).write_text(generate_index(repos_data))
    print(f"Index written to {args.output}", file=sys.stderr)

if __name__ == "__main__":
    main()
