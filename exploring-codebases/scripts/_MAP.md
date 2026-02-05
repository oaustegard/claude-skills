# scripts/
*Files: 1*

## Files

### search.py
> Imports: `subprocess, json, sys, os, dataclasses`...
- **HybridRetriever** (C) :71
  - **__init__** (m) `(self)` :72
  - **_get_language** (m) `(self, file_path: str)` :75
  - **_get_parser** (m) `(self, language: str)` :79
  - **_run_ripgrep** (m) `(self, query: str, path: str, glob: Optional[str] = None)` :88
  - **_get_node_name** (m) `(self, node, source_bytes: bytes)` :132
  - **_extract_signature** (m) `(self, node, source_bytes: bytes, language: str)` :146
  - **_extract_python_signature** (m) `(self, node, source_bytes: bytes)` :160
  - **_extract_js_signature** (m) `(self, node, source_bytes: bytes)` :203
  - **_extract_go_signature** (m) `(self, node, source_bytes: bytes)` :215
  - **_get_node_at_line** (m) `(self, root_node, line_number: int, language: str)` :226
  - **_expand_context** (m) `(self, file_path: str, line_number: int, signatures_only: bool = True)` :263
  - **search** (m) `(self, query: str, path: str = ".", glob: Optional[str] = None, signatures_only: bool = True)` :314
- **main** (f) `()` :333

