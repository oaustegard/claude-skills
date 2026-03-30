# scripts/
*Files: 6*

## Files

### code_rag.py
> Imports: `os, re, sys, json, time`...
- **main** (f) `()` :566

### context.py
> Imports: `os, re, dataclasses, typing`
- **parse_map_file** (f) `(map_path: str)` :53
- **find_map_for_file** (f) `(file_path: str, search_root: str)` :100
- **expand_match** (f) `(file_path: str, line_number: int, search_root: str,
                 signatures_only: bool = True)` :114
- **deduplicate_contexts** (f) `(contexts: List[CodeContext])` :229

### ngram_index.py
> Imports: `os, re, sre_parse, struct, subprocess`...
- **NgramIndex** (C) :58
  - **__init__** (m) `(self, weight_fn=None)` :66
  - **_assign_id** (m) `(self, path: str)` :89
  - **_should_index** (m) `(self, path: str, skip_dirs: Set[str])` :99
  - **build** (m) `(
        self,
        root: str,
        skip_dirs: Optional[Set[str]] = None,
        use_frequency_weights: bool = True,
        verbose: bool = False,
    )` :126
  - **_query_literal** (m) `(self, literal: bytes)` :226
  - **_eval_plan** (m) `(self, plan: "QueryPlan")` :256
  - **search** (m) `(
        self,
        pattern: str,
        root: str,
        max_results: int = 100,
        verbose: bool = False,
    )` :290
- **QueryPlan** (C) :343
  - **__init__** (m) `(self, op: str, children=None, literal: bytes = None)` :353
  - **__repr__** (m) `(self)` :358
- **extract_query_plan** (f) `(pattern: str)` :365
- **extract_literals** (f) `(pattern: str)` :455
- **verify_candidates** (f) `(
    pattern: str,
    candidate_files: List[str],
    root: str,
    max_results: int = 100,
    verbose: bool = False,
)` :478

### resolve.py
> Imports: `os, shutil, subprocess, tarfile, tempfile`...
- **resolve** (f) `(source: str, branch: str = "main")` :22
- **count_files** (f) `(root: str, skip_dirs: set = None)` :150

### search.py
> Imports: `argparse, json, os, re, subprocess`...
- **detect_mode** (f) `(query: str)` :54
- **run_map** (f) `(root: str, skip: str = None)` :81
- **search_regex** (f) `(root: str, queries: list, expand: bool = False,
                 benchmark: bool = False, verbose: bool = False,
                 skip_dirs: set = None)` :112
- **search_semantic** (f) `(root: str, queries: list, expand: bool = False,
                    verbose: bool = False, skip_dirs: set = None)` :157
- **format_results** (f) `(results: dict, root: str, output_json: bool = False)` :250
- **main** (f) `()` :296

### sparse_ngrams.py
> Imports: `zlib, typing, collections`
- **weight_crc32** (f) `(a: int, b: int)` :20
- **FrequencyWeights** (C) :25
  - **__init__** (m) `(self)` :33
  - **train** (m) `(self, data: bytes)` :38
  - **freeze** (m) `(self)` :46
  - **weight** (m) `(self, a: int, b: int)` :52
  - **save** (m) `(self)` :67
- **compute_weights** (f) `(
    text: bytes, weight_fn=weight_crc32
)` :91
- **build_all** (f) `(weights: List[int])` :100
- **build_covering** (f) `(weights: List[int])` :140
- **ngram_text** (f) `(text: bytes, start: int, end: int)` :186
- **ngram_hash** (f) `(text: bytes, start: int, end: int)` :195

