# scripts/
*Files: 1*

## Files

### codemap.py
> Imports: `os, sys, pathlib, dataclasses, tree_sitter_language_pack`
- **get_language** (f) `(filepath: Path)`
- **get_node_text** (f) `(node, source: bytes)`
- **extract_python** (f) `(tree, source: bytes)`
- **extract_typescript** (f) `(tree, source: bytes)`
- **extract_go** (f) `(tree, source: bytes)`
- **extract_rust** (f) `(tree, source: bytes)`
- **extract_ruby** (f) `(tree, source: bytes)`
- **extract_java** (f) `(tree, source: bytes)`
- **extract_html_javascript** (f) `(tree, source: bytes)`
- **analyze_file** (f) `(filepath: Path)`
- **format_symbol** (f) `(symbol: Symbol, indent: int = 0)`
- **generate_map_for_directory** (f) `(dirpath: Path, skip_dirs: set[str])`
- **generate_maps** (f) `(root: Path, skip_dirs: set[str], dry_run: bool = False)`
- **main** (f) `()`

