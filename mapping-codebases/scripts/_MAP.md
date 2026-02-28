# scripts/
*Files: 1*

## Files

### codemap.py
> Imports: `os, sys, pathlib, dataclasses, tree_sitter_language_pack`
- **get_language** (f) `(filepath: Path)` :66
- **get_node_text** (f) `(node, source: bytes)` :69
- **extract_python** (f) `(tree, source: bytes)` :72
- **extract_typescript** (f) `(tree, source: bytes)` :152
- **extract_go** (f) `(tree, source: bytes)` :291
- **extract_rust** (f) `(tree, source: bytes)` :392
- **extract_ruby** (f) `(tree, source: bytes)` :492
- **extract_java** (f) `(tree, source: bytes)` :575
- **extract_html_javascript** (f) `(tree, source: bytes)` :611
- **extract_markdown** (f) `(tree, source: bytes)` :705
- **analyze_file** (f) `(filepath: Path)` :763
- **format_symbol** (f) `(symbol: Symbol, indent: int = 0)` :788
- **generate_map_for_directory** (f) `(dirpath: Path, skip_dirs: set[str])` :813
- **generate_maps** (f) `(root: Path, skip_dirs: set[str], dry_run: bool = False)` :892
- **main** (f) `()` :917

