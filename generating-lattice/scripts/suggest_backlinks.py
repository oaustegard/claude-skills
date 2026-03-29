#!/usr/bin/env python3
"""
suggest_backlinks.py — Suggest @lat: back-link placements in source code.

Parses [[src/...]] wiki links from lat.md/ files, locates referenced symbols
in source, checks for existing @lat: comments, and suggests where to add
missing back-links.

Usage:
    python3 suggest_backlinks.py /path/to/repo [--apply] [--dry-run]

Options:
    --apply     Write @lat: comments directly into source files
    --dry-run   Show what --apply would do without writing (default)
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

# Wiki link pattern: [[src/path/to/file.ext#Symbol#Method]]
WIKI_LINK_RE = re.compile(r'\[\[(src/[^\]|]+)\]\]')

# @lat: comment pattern
LAT_COMMENT_RE = re.compile(r'(?://|#)\s*@lat:\s*\[\[([^\]]+)\]\]')

# Comment prefix by file extension
COMMENT_PREFIX = {
    '.js': '//', '.jsx': '//', '.ts': '//', '.tsx': '//',
    '.go': '//', '.rs': '//', '.c': '//', '.h': '//',
    '.py': '#', '.rb': '#', '.sh': '#',
}

# Symbol declaration patterns by language (simplified — find line containing def/function/class/const)
SYMBOL_PATTERNS = {
    '.js':  r'(?:export\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+{symbol}\b',
    '.jsx': r'(?:export\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+{symbol}\b',
    '.ts':  r'(?:export\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+{symbol}\b',
    '.tsx': r'(?:export\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+{symbol}\b',
    '.py':  r'(?:def|class|async\s+def)\s+{symbol}\b',
    '.rs':  r'(?:pub\s+)?(?:fn|struct|enum|trait|const|static|type|impl)\s+{symbol}\b',
    '.go':  r'(?:func|type|const|var)\s+(?:\([^)]+\)\s+)?{symbol}\b',
    '.c':   r'(?:struct|enum|typedef|#define)\s+{symbol}\b|{symbol}\s*\(',
    '.h':   r'(?:struct|enum|typedef|#define)\s+{symbol}\b|{symbol}\s*\(',
}


def parse_source_refs(lat_dir):
    """Extract all [[src/...]] wiki links from lat.md/ files with their section context."""
    refs = []  # list of (source_path, symbol_path, section_id, lat_file)
    
    for md_file in sorted(lat_dir.glob('**/*.md')):
        rel_path = md_file.relative_to(lat_dir)
        current_sections = []
        
        with open(md_file) as f:
            for line in f:
                # Track section headings
                heading_match = re.match(r'^(#{1,6})\s+(.+)', line)
                if heading_match:
                    depth = len(heading_match.group(1))
                    heading = heading_match.group(2).strip()
                    # Trim to current depth
                    current_sections = current_sections[:depth-1] + [heading]
                
                # Find wiki links to source
                for match in WIKI_LINK_RE.finditer(line):
                    target = match.group(1)
                    parts = target.split('#')
                    source_file = parts[0]
                    symbol_path = '#'.join(parts[1:]) if len(parts) > 1 else None
                    
                    # Build section id
                    file_stem = str(rel_path).replace('.md', '')
                    section_id = file_stem + ('#' + '#'.join(current_sections) if current_sections else '')
                    
                    refs.append({
                        'source_file': source_file,
                        'symbol': symbol_path,
                        'section_id': section_id,
                        'lat_file': str(rel_path),
                    })
    
    return refs


def find_symbol_line(file_path, symbol_name, ext):
    """Find the line number where a symbol is defined."""
    pattern_template = SYMBOL_PATTERNS.get(ext)
    if not pattern_template:
        return None
    
    # Use the last segment of the symbol path (e.g., "App#listen" → "listen")
    leaf_symbol = symbol_name.split('#')[-1] if symbol_name else None
    if not leaf_symbol:
        return None
    
    pattern = re.compile(pattern_template.format(symbol=re.escape(leaf_symbol)))
    
    try:
        with open(file_path) as f:
            for i, line in enumerate(f, 1):
                if pattern.search(line):
                    return i
    except (OSError, UnicodeDecodeError):
        pass
    
    return None


def find_existing_backlinks(file_path):
    """Find all existing @lat: comments in a source file."""
    backlinks = {}  # line_number → section_id
    try:
        with open(file_path) as f:
            for i, line in enumerate(f, 1):
                match = LAT_COMMENT_RE.search(line)
                if match:
                    backlinks[i] = match.group(1)
    except (OSError, UnicodeDecodeError):
        pass
    return backlinks


def suggest_backlinks(project_root, refs):
    """Analyze refs and produce suggestions for missing @lat: back-links."""
    suggestions = []
    already_linked = []
    not_found = []
    
    # Group refs by source file
    by_file = defaultdict(list)
    for ref in refs:
        by_file[ref['source_file']].append(ref)
    
    for source_file, file_refs in sorted(by_file.items()):
        full_path = project_root / source_file
        if not full_path.exists():
            for ref in file_refs:
                not_found.append(ref)
            continue
        
        ext = full_path.suffix
        prefix = COMMENT_PREFIX.get(ext)
        if not prefix:
            continue
        
        existing = find_existing_backlinks(full_path)
        existing_targets = set(existing.values())
        
        for ref in file_refs:
            if not ref['symbol']:
                # File-level link, no specific symbol to annotate
                continue
            
            # Check if this section is already back-linked anywhere in the file
            if ref['section_id'] in existing_targets:
                already_linked.append(ref)
                continue
            
            # Find where the symbol is defined
            line_num = find_symbol_line(full_path, ref['symbol'], ext)
            if line_num is None:
                not_found.append(ref)
                continue
            
            suggestions.append({
                **ref,
                'line': line_num,
                'comment': f'{prefix} @lat: [[{ref["section_id"]}]]',
                'full_path': str(full_path),
            })
    
    return suggestions, already_linked, not_found


def apply_backlinks(suggestions):
    """Write @lat: comments into source files."""
    # Group by file, sort by line descending (insert bottom-up to preserve line numbers)
    by_file = defaultdict(list)
    for s in suggestions:
        by_file[s['full_path']].append(s)
    
    for file_path, file_suggestions in by_file.items():
        with open(file_path) as f:
            lines = f.readlines()
        
        # Sort by line number descending so insertions don't shift earlier line numbers
        for s in sorted(file_suggestions, key=lambda x: x['line'], reverse=True):
            insert_at = s['line'] - 1  # 0-indexed
            indent = re.match(r'^(\s*)', lines[insert_at]).group(1) if insert_at < len(lines) else ''
            lines.insert(insert_at, f'{indent}{s["comment"]}\n')
        
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print(f'  Updated {file_path} ({len(file_suggestions)} back-links)')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    project_root = Path(sys.argv[1]).resolve()
    apply = '--apply' in sys.argv
    
    lat_dir = project_root / 'lat.md'
    if not lat_dir.is_dir():
        print(f'Error: {lat_dir} not found. Generate lat.md/ files first.')
        sys.exit(1)
    
    print(f'Scanning {lat_dir} for [[src/...]] wiki links...\n')
    
    refs = parse_source_refs(lat_dir)
    if not refs:
        print('No source code references found in lat.md/ files.')
        sys.exit(0)
    
    print(f'Found {len(refs)} source code references across lat.md/ files.\n')
    
    suggestions, already_linked, not_found = suggest_backlinks(project_root, refs)
    
    # Report
    if already_linked:
        print(f'Already back-linked ({len(already_linked)}):')
        for ref in already_linked:
            print(f'  ✓ {ref["source_file"]}#{ref["symbol"]} ← [[{ref["section_id"]}]]')
        print()
    
    if suggestions:
        print(f'Missing back-links ({len(suggestions)}):')
        for s in suggestions:
            print(f'  {s["source_file"]}:{s["line"]}')
            print(f'    Symbol: {s["symbol"]}')
            print(f'    Add:    {s["comment"]}')
            print()
        
        if apply:
            print('Applying back-links...')
            apply_backlinks(suggestions)
            print(f'\nDone. Run `lat check` to verify.')
        else:
            print(f'Run with --apply to write these {len(suggestions)} back-links into source files.')
            print('Review the suggestions first — placement is a judgment call.')
    else:
        print('All source code references have back-links. ✓')
    
    if not_found:
        print(f'\nCould not locate ({len(not_found)}):')
        for ref in not_found:
            sym = f'#{ref["symbol"]}' if ref['symbol'] else ''
            print(f'  ? {ref["source_file"]}{sym} (referenced in {ref["lat_file"]})')


if __name__ == '__main__':
    main()
