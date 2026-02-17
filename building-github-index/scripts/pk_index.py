#!/usr/bin/env python3
"""
Project Knowledge Index Generator
Produces flat, token-efficient indexes for Claude project knowledge.
Extracts semantic info from code (AST) and docs (headings).
"""

import json
import os
import sys
import tarfile
import tempfile
import urllib.request
from collections import defaultdict
from pathlib import Path
import re

try:
    from tree_sitter_language_pack import get_parser
    TS_AVAILABLE = True
except ImportError:
    TS_AVAILABLE = False

LANG_MAP = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.c': 'c', '.h': 'c', '.go': 'go', '.rs': 'rust'}

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 
             'dist', 'build', 'test', 'tests', 'docs', '.github',
             'vendor', 'third_party', 'fixtures', 'examples'}

def fetch_tarball(owner: str, repo: str, ref: str = 'main') -> bytes:
    url = f'https://api.github.com/repos/{owner}/{repo}/tarball/{ref}'
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req) as resp:
        return resp.read()

def extract_md_topics(content: str) -> list[str]:
    """Extract h1/h2 headings as topics."""
    headings = re.findall(r'^#{1,2}\s+(.+)$', content, re.MULTILINE)
    # Clean and dedupe
    seen = set()
    topics = []
    for h in headings[:8]:
        h = h.strip().lower()
        if h not in seen and len(h) < 60:
            seen.add(h)
            topics.append(h)
    return topics

def extract_py_symbols(content: bytes, parser) -> list[str]:
    """Extract public class/function names from Python."""
    tree = parser.parse(content)
    symbols = []
    
    def get_text(node):
        return content[node.start_byte:node.end_byte].decode('utf-8', errors='replace')
    
    for node in tree.root_node.children:
        if node.type in ('function_definition', 'class_definition'):
            name_node = node.child_by_field_name('name')
            if name_node:
                name = get_text(name_node)
                if not name.startswith('_'):
                    symbols.append(name)
    return symbols[:10]  # Limit

def extract_js_symbols(content: bytes, parser) -> list[str]:
    """Extract exported names from JavaScript (ES6 + CommonJS)."""
    tree = parser.parse(content)
    symbols = []
    
    def get_text(node):
        return content[node.start_byte:node.end_byte].decode('utf-8', errors='replace')
    
    def walk(node):
        # ES6: export function/class/const
        if node.type == 'export_statement':
            for child in node.children:
                if child.type in ('function_declaration', 'class_declaration'):
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        symbols.append(get_text(name_node))
        # CommonJS: module.exports = { ... } or exports.foo = ...
        if node.type == 'assignment_expression':
            left = node.child_by_field_name('left')
            if left:
                left_text = get_text(left)
                if 'module.exports' in left_text or left_text.startswith('exports.'):
                    # Try to get the assigned name
                    if '.' in left_text:
                        name = left_text.split('.')[-1]
                        if name and name not in ('exports', 'module'):
                            symbols.append(name)
        for child in node.children:
            walk(child)
    
    walk(tree.root_node)
    return symbols[:10]

def process_repo(owner: str, repo: str, ref: str = 'main', output: str = None):
    """Generate condensed index for project knowledge."""
    
    print(f"Fetching {owner}/{repo}@{ref}...", file=sys.stderr)
    tarball_data = fetch_tarball(owner, repo, ref)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tarpath = Path(tmpdir) / 'repo.tar.gz'
        tarpath.write_bytes(tarball_data)
        
        with tarfile.open(tarpath, 'r:gz') as tar:
            tar.extractall(tmpdir)
        
        extracted = [d for d in Path(tmpdir).iterdir() if d.is_dir()]
        repo_root = extracted[0]
        
        # Collect by category
        entries = []  # (category, path, description)
        
        for filepath in repo_root.rglob('*'):
            if not filepath.is_file():
                continue
            
            rel_path = filepath.relative_to(repo_root)
            if any(part in SKIP_DIRS for part in rel_path.parts):
                continue
            
            suffix = filepath.suffix.lower()
            
            try:
                content = filepath.read_bytes()
            except:
                continue
            
            # Markdown files
            if suffix in ('.md', '.mdx', '.qmd'):
                topics = extract_md_topics(content.decode('utf-8', errors='replace'))
                if topics:
                    desc = ', '.join(topics[:4])
                    entries.append((str(rel_path.parent or 'root'), str(rel_path), desc))
                continue
            
            # Code files
            if suffix in LANG_MAP and TS_AVAILABLE:
                lang = LANG_MAP[suffix]
                try:
                    parser = get_parser(lang)
                    if lang == 'python':
                        symbols = extract_py_symbols(content, parser)
                    elif lang in ('javascript', 'typescript'):
                        symbols = extract_js_symbols(content, parser)
                    else:
                        symbols = []
                    
                    if symbols:
                        desc = ', '.join(symbols[:5])
                        if len(symbols) > 5:
                            desc += f' +{len(symbols)-5}'
                        entries.append((str(rel_path.parent or 'root'), str(rel_path), desc))
                except:
                    pass
        
        print(f"Indexed {len(entries)} files", file=sys.stderr)
        
        # Generate output
        output_path = output or f'/home/claude/{repo}_pk.md'
        generate_pk_output(owner, repo, ref, entries, output_path)
        print(f"Written to {output_path}", file=sys.stderr)

def generate_pk_output(owner: str, repo: str, ref: str, entries: list, output_path: str):
    """Generate project-knowledge-optimized index."""
    lines = [
        f"# {repo} Index",
        f"Repo: https://github.com/{owner}/{repo} | Branch: `{ref}`",
        "",
        f'Fetch: `curl -s "https://api.github.com/repos/{owner}/{repo}/contents/PATH?ref={ref}" -H "Accept: application/vnd.github+json" | python3 -c "import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)[\'content\']).decode())"`',
        "",
    ]
    
    # Group by category
    by_cat = defaultdict(list)
    for cat, path, desc in entries:
        by_cat[cat].append((path, desc))
    
    for cat in sorted(by_cat.keys()):
        items = by_cat[cat]
        lines.append(f"## {cat}/")
        for path, desc in items[:15]:  # Limit per category
            lines.append(f"- `{path}` — {desc}")
        if len(items) > 15:
            lines.append(f"- *+{len(items)-15} more*")
        lines.append("")
    
    Path(output_path).write_text('\n'.join(lines))

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('repo', help='owner/repo')
    p.add_argument('-r', '--ref', default='main')
    p.add_argument('-o', '--output')
    args = p.parse_args()
    owner, repo = args.repo.split('/')
    process_repo(owner, repo, args.ref, args.output)
