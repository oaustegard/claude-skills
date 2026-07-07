#!/usr/bin/env python3
"""
annotate_maps.py — Add lat.md cross-references to _MAP.md files.

Scans source files for @lat: comments, then annotates _MAP.md file headers
with links to the lat.md sections that document them.

Keeps mapping-codebases and generating-lattice decoupled: codemap.py has no
lat.md awareness; this post-processor decorates existing _MAP.md output.

Usage:
    python3 annotate_maps.py /path/to/repo [--dry-run]

Options:
    --dry-run   Show what would change without writing
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

# @lat: comment pattern — matches both // and # styles
LAT_COMMENT_RE = re.compile(r'(?://|#)\s*@lat:\s*\[\[([^\]]+)\]\]')

# _MAP.md file header: ### filename.ext
MAP_FILE_HEADER_RE = re.compile(r'^### (.+)$')

# Existing annotation line (to detect and update)
ANNOTATION_RE = re.compile(r'^> Documented in: ')


def scan_lat_comments(project_root):
    """Scan all source files for @lat: comments.

    Returns dict: {relative_file_path: [section_id, ...]}
    """
    lat_refs = defaultdict(list)

    # Walk the project, skipping common non-source dirs
    skip_dirs = {'.git', 'node_modules', 'vendor', '__pycache__', '.venv',
                 'venv', 'dist', 'build', '.next', 'target', 'lat.md'}

    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith('.')]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            # Only scan text files with known comment syntax
            if fpath.suffix not in {'.py', '.js', '.jsx', '.ts', '.tsx', '.go',
                                     '.rs', '.c', '.h', '.rb', '.sh'}:
                continue

            try:
                with open(fpath) as f:
                    for line in f:
                        match = LAT_COMMENT_RE.search(line)
                        if match:
                            section_id = match.group(1)
                            rel_path = str(fpath.relative_to(project_root))
                            if section_id not in lat_refs[rel_path]:
                                lat_refs[rel_path].append(section_id)
            except (OSError, UnicodeDecodeError):
                pass

    return dict(lat_refs)


def annotate_map_file(map_path, project_root, lat_refs, dry_run=False):
    """Add 'Documented in:' lines to a _MAP.md file.

    Returns number of annotations added/updated.
    """
    map_dir = map_path.parent.relative_to(project_root)

    with open(map_path) as f:
        lines = f.readlines()

    new_lines = []
    changes = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        new_lines.append(line)

        # Check for file header
        fh = MAP_FILE_HEADER_RE.match(line.rstrip())
        if fh:
            filename = fh.group(1)
            rel_file = str(map_dir / filename)
            sections = lat_refs.get(rel_file, [])

            # Skip any existing annotation line(s) right after header
            while i + 1 < len(lines) and ANNOTATION_RE.match(lines[i + 1].rstrip()):
                i += 1  # consume old annotation

            if sections:
                # Format section refs as [[lat.md/section]]
                refs = ', '.join(f'[[{s}]]' for s in sorted(sections))
                new_lines.append(f'> Documented in: {refs}\n')
                changes += 1

        i += 1

    if changes > 0 and not dry_run:
        with open(map_path, 'w') as f:
            f.writelines(new_lines)

    return changes


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    dry_run = '--dry-run' in sys.argv

    lat_dir = project_root / 'lat.md'
    if not lat_dir.is_dir():
        print(f'Warning: {lat_dir} not found. No lat.md cross-references to add.')
        sys.exit(0)

    # Phase 1: Scan source for @lat: comments
    lat_refs = scan_lat_comments(project_root)
    total_refs = sum(len(v) for v in lat_refs.values())
    print(f'Found @lat: comments in {len(lat_refs)} files ({total_refs} section references).\n')

    if not lat_refs:
        print('No @lat: comments found. Run suggest_backlinks.py --apply first.')
        sys.exit(0)

    # Phase 2: Annotate _MAP.md files
    total_changes = 0
    for map_path in sorted(project_root.rglob('_MAP.md')):
        changes = annotate_map_file(map_path, project_root, lat_refs, dry_run)
        if changes:
            action = 'Would annotate' if dry_run else 'Annotated'
            print(f'  {action}: {map_path.relative_to(project_root)} ({changes} files)')
            total_changes += changes

    if total_changes:
        action = 'would annotate' if dry_run else 'annotated'
        print(f'\n{total_changes} file entries {action} across _MAP.md files.')
    else:
        print('No _MAP.md entries needed annotation (files without @lat: comments).')


if __name__ == '__main__':
    main()
