#!/usr/bin/env python3
"""
Analyze the claude-skills repository to count various artifacts
for ROI calculation.
"""

import os
import json
from pathlib import Path
from collections import defaultdict

def count_lines(filepath):
    """Count non-empty lines in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return len([line for line in f if line.strip()])
    except:
        return 0

def analyze_repo(root_dir='.'):
    """Analyze repository structure and count artifacts."""

    stats = {
        'markdown': {'files': 0, 'lines': 0, 'breakdown': defaultdict(int)},
        'code': {'files': 0, 'lines': 0, 'breakdown': defaultdict(lambda: {'files': 0, 'lines': 0})},
        'skills': [],
        'workflows': {'files': 0, 'lines': 0},
        'total_directories': 0
    }

    root = Path(root_dir)

    # Identify skill directories (top-level dirs with SKILL.md)
    for item in root.iterdir():
        if item.is_dir() and item.name not in ['.git', '.github', '.claude', 'uploads', '__pycache__']:
            stats['total_directories'] += 1
            skill_md = item / 'SKILL.md'
            if skill_md.exists():
                lines = count_lines(skill_md)
                stats['skills'].append({
                    'name': item.name,
                    'lines': lines
                })

    # Count all files
    for filepath in root.rglob('*'):
        if filepath.is_file() and '.git' not in str(filepath):
            ext = filepath.suffix.lower()
            lines = count_lines(filepath)

            # Categorize markdown files
            if ext == '.md':
                stats['markdown']['files'] += 1
                stats['markdown']['lines'] += lines

                # Breakdown by type
                if filepath.name == 'SKILL.md':
                    stats['markdown']['breakdown']['skill_definitions'] += lines
                elif filepath.name in ['README.md', 'CLAUDE.md', 'AGENTS.md', 'DEVLOG.md']:
                    stats['markdown']['breakdown']['documentation'] += lines
                elif 'references/' in str(filepath):
                    stats['markdown']['breakdown']['references'] += lines
                else:
                    stats['markdown']['breakdown']['other'] += lines

            # Categorize code files
            elif ext in ['.py', '.sh', '.js', '.mjs', '.ts']:
                stats['code']['files'] += 1
                stats['code']['lines'] += lines
                stats['code']['breakdown'][ext]['files'] += 1
                stats['code']['breakdown'][ext]['lines'] += lines

            # Categorize workflow files
            elif ext in ['.yml', '.yaml'] and '.github' in str(filepath):
                stats['workflows']['files'] += 1
                stats['workflows']['lines'] += lines

    return stats

def print_stats(stats):
    """Print formatted statistics."""
    print("\n" + "="*60)
    print("REPOSITORY ANALYSIS")
    print("="*60)

    print(f"\nSkills Identified: {len(stats['skills'])}")
    print(f"Total Directories: {stats['total_directories']}")

    print("\n--- MARKDOWN FILES (Architecture/Planning) ---")
    print(f"Total Files: {stats['markdown']['files']}")
    print(f"Total Lines: {stats['markdown']['lines']:,}")
    print("\nBreakdown:")
    for category, lines in sorted(stats['markdown']['breakdown'].items()):
        print(f"  {category.replace('_', ' ').title()}: {lines:,} lines")

    print("\n--- CODE FILES (Implementation) ---")
    print(f"Total Files: {stats['code']['files']}")
    print(f"Total Lines: {stats['code']['lines']:,}")
    print("\nBreakdown by Language:")
    for ext, data in sorted(stats['code']['breakdown'].items()):
        print(f"  {ext}: {data['files']} files, {data['lines']:,} lines")

    print("\n--- WORKFLOW FILES (CI/CD) ---")
    print(f"Total Files: {stats['workflows']['files']}")
    print(f"Total Lines: {stats['workflows']['lines']:,}")

    print("\n--- SKILLS DETAIL ---")
    for skill in sorted(stats['skills'], key=lambda x: x['lines'], reverse=True):
        print(f"  {skill['name']}: {skill['lines']:,} lines")

    print("\n" + "="*60)

if __name__ == '__main__':
    stats = analyze_repo()
    print_stats(stats)

    # Save to JSON for further processing
    with open('repo_stats.json', 'w') as f:
        json.dump(stats, f, indent=2)

    print("\nStats saved to repo_stats.json")
