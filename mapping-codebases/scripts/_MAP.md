# scripts/
*Files: 1*

## Files

### codemap.py
> Imports: `os, sys, subprocess, json, platform`...
- **get_language** (f) `(filepath: Path)` :191
- **get_node_text** (f) `(node, source: bytes)` :194
- **extract_python** (f) `(tree, source: bytes)` :197
- **extract_typescript** (f) `(tree, source: bytes)` :277
- **extract_go** (f) `(tree, source: bytes)` :416
- **extract_rust** (f) `(tree, source: bytes)` :517
- **extract_ruby** (f) `(tree, source: bytes)` :617
- **extract_java** (f) `(tree, source: bytes)` :700
- **extract_html_javascript** (f) `(tree, source: bytes)` :736
- **extract_markdown** (f) `(tree, source: bytes)` :830
- **analyze_file** (f) `(filepath: Path)` :889
- **format_symbol** (f) `(symbol: Symbol, indent: int = 0)` :914
- **generate_map_for_directory** (f) `(dirpath: Path, skip_dirs: set[str])` :939
- **generate_maps** (f) `(root: Path, skip_dirs: set[str], dry_run: bool = False)` :1019
- **main** (f) `()` :1063

