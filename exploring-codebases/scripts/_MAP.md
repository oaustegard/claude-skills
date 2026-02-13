# scripts/
*Files: 1*

## Files

### search.py
> Imports: `subprocess, json, sys, os, re`...
- **HybridRetriever** (C) :337
  - **__init__** (m) `(self, use_maps: bool = False, search_root: str = ".")` :338
  - **_get_language** (m) `(self, file_path: str)` :343
  - **_get_parser** (m) `(self, language: str)` :347
  - **_run_ripgrep** (m) `(self, query: str, path: str, glob: Optional[str] = None)` :356
  - **_get_node_name** (m) `(self, node, source_bytes: bytes)` :400
  - **_extract_signature** (m) `(self, node, source_bytes: bytes, language: str)` :414
  - **_extract_python_signature** (m) `(self, node, source_bytes: bytes)` :428
  - **_extract_js_signature** (m) `(self, node, source_bytes: bytes)` :471
  - **_extract_go_signature** (m) `(self, node, source_bytes: bytes)` :483
  - **_get_node_at_line** (m) `(self, root_node, line_number: int, language: str)` :494
  - **_expand_context** (m) `(self, file_path: str, line_number: int, signatures_only: bool = True)` :531
  - **search** (m) `(self, query: str, path: str = ".", glob: Optional[str] = None, signatures_only: bool = True)` :577
- **main** (f) `()` :604

