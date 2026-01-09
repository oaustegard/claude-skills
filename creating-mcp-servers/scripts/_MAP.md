# scripts/
*Files: 1*

## Files

### create_mcpb.py
> Imports: `argparse, json, zipfile, pathlib, typing`...
- **extract_server_name** (f) `(server_path: Path)` :46
- **extract_dependencies** (f) `(requirements_file: Path)` :58
- **create_manifest** (f) `(
    server_path: Path,
    name: str | None = None,
    version: str = "1.0.0",
    description: str | None = None,
    author: str | None = None,
    license: str = "MIT",
    homepage: str | None = None,
    dependencies: List[str] | None = None,
    env_vars: List[str] | None = None,
    tags: List[str] | None = None,
)` :70
- **create_bundle** (f) `(
    server_path: Path,
    output_path: Path,
    manifest: Dict[str, Any],
    include_files: List[str] | None = None,
    exclude_patterns: List[str] | None = None,
)` :138
- **validate_bundle** (f) `(bundle_path: Path)` :209
- **main** (f) `()` :243

