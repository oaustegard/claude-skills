# scripts/
*Files: 1*

## Files

### search.py
> Imports: `subprocess, json, sys, os, re`...
- **HybridRetriever** (C) :287
  - **__init__** (m) `(self, use_maps: bool = False, search_root: str = ".")` :288
  - **_get_language** (m) `(self, file_path: str)` :293
  - **_get_parser** (m) `(self, language: str)` :297
  - **_run_ripgrep** (m) `(self, query: str, path: str, glob: Optional[str] = None)` :306
  - **_get_node_name** (m) `(self, node, source_bytes: bytes)` :350
  - **_extract_signature** (m) `(self, node, source_bytes: bytes, language: str)` :364
  - **_extract_python_signature** (m) `(self, node, source_bytes: bytes)` :378
  - **_extract_js_signature** (m) `(self, node, source_bytes: bytes)` :421
  - **_extract_go_signature** (m) `(self, node, source_bytes: bytes)` :433
  - **_get_node_at_line** (m) `(self, root_node, line_number: int, language: str)` :444
  - **_expand_context** (m) `(self, file_path: str, line_number: int, signatures_only: bool = True)` :481
  - **search** (m) `(self, query: str, path: str = ".", glob: Optional[str] = None, signatures_only: bool = True)` :527
- **main** (f) `()` :554

