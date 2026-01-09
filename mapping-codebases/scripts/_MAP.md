# scripts/
*Files: 1*

## Files

### codemap.py
> Imports: `os, sys, pathlib, dataclasses, tree_sitter_language_pack`
- **get_language** (f) `(filepath: Path)` :58
- **get_node_text** (f) `(node, source: bytes)` :61
- **extract_python** (f) `(tree, source: bytes)` :64
- **extract_typescript** (f) `(tree, source: bytes)` :144
- **extract_go** (f) `(tree, source: bytes)` :223
- **extract_rust** (f) `(tree, source: bytes)` :247
- **extract_ruby** (f) `(tree, source: bytes)` :290
- **extract_java** (f) `(tree, source: bytes)` :324
- **extract_html_javascript** (f) `(tree, source: bytes)` :360
- **extract_markdown** (f) `(tree, source: bytes)` :454
- **analyze_file** (f) `(filepath: Path)` :508
- **format_symbol** (f) `(symbol: Symbol, indent: int = 0)` :531
- **generate_map_for_directory** (f) `(dirpath: Path, skip_dirs: set[str])` :556
- **generate_maps** (f) `(root: Path, skip_dirs: set[str], dry_run: bool = False)` :635
- **main** (f) `()` :660

