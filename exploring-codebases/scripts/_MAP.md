# scripts/
*Files: 1*

## Files

### search.py
> Imports: `subprocess, json, sys, os, re`...
- **HybridRetriever** (C) :338
  - **__init__** (m) `(self, use_maps: bool = False, search_root: str = ".")` :339
  - **_get_language** (m) `(self, file_path: str)` :344
  - **_get_parser** (m) `(self, language: str)` :348
  - **_run_ripgrep** (m) `(self, query: str, path: str, glob: Optional[str] = None)` :357
  - **_get_node_name** (m) `(self, node, source_bytes: bytes)` :401
  - **_extract_signature** (m) `(self, node, source_bytes: bytes, language: str)` :415
  - **_extract_python_signature** (m) `(self, node, source_bytes: bytes)` :429
  - **_extract_js_signature** (m) `(self, node, source_bytes: bytes)` :472
  - **_extract_go_signature** (m) `(self, node, source_bytes: bytes)` :484
  - **_get_node_at_line** (m) `(self, root_node, line_number: int, language: str)` :495
  - **_expand_context** (m) `(self, file_path: str, line_number: int, signatures_only: bool = True)` :532
  - **search** (m) `(self, query: str, path: str = ".", glob: Optional[str] = None, signatures_only: bool = True)` :578
- **main** (f) `()` :605

