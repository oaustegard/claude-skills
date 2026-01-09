# scripts/
*Files: 2*

## Files

### frontmatter_utils.py
> Imports: `re, yaml, pathlib, typing`
- **parse_skill_md** (f) `(skill_md_path: Path)`
- **write_skill_md** (f) `(skill_md_path: Path, frontmatter: Dict[str, Any], body: str)`
- **extract_version** (f) `(skill_dir: Path)`
- **validate_version_format** (f) `(version: str)`

### migrate-version-to-frontmatter.py
> Imports: `sys, argparse, pathlib, frontmatter_utils`
- **migrate_skill** (f) `(skill_dir: Path, dry_run: bool = False)`
- **find_skill_directories** (f) `(repo_root: Path)`
- **main** (f) `()`

