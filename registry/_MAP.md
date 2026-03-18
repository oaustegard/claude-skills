# registry/
*Files: 4*

## Files

### __init__.py
- *No top-level symbols*

### generate.py
> Imports: `json, subprocess, sys, datetime, pathlib`...
- **discover_skill_dirs** (f) `(root: Path)` :33
- **get_last_updated** (f) `(skill_dir: Path)` :48
- **list_skill_files** (f) `(skill_dir: Path)` :62
- **build_download_url** (f) `(name: str, version: Optional[str])` :76
- **normalize_list** (f) `(value)` :83
- **build_entry** (f) `(skill_dir: Path)` :94
- **generate** (f) `(root: Path)` :125
- **main** (f) `()` :149

### llms_txt.py
> Imports: `.schema`
- **render_llms_txt** (f) `(registry: Registry)` :6

### schema.py
> Imports: `dataclasses, typing`
- *No top-level symbols*

