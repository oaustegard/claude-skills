# scripts/
*Files: 2*

## Files

### frontmatter_utils.py
> Imports: `re, yaml, pathlib, typing`
- **parse_skill_md** (f) `(skill_md_path: Path)` :10
- **write_skill_md** (f) `(skill_md_path: Path, frontmatter: Dict[str, Any], body: str)` :52
- **extract_version** (f) `(skill_dir: Path)` :80
- **validate_version_format** (f) `(version: str)` :112

### migrate-version-to-frontmatter.py
> Imports: `sys, argparse, pathlib, frontmatter_utils`
- **migrate_skill** (f) `(skill_dir: Path, dry_run: bool = False)` :22
- **find_skill_directories** (f) `(repo_root: Path)` :91
- **main** (f) `()` :107

