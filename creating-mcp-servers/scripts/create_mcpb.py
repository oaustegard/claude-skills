#!/usr/bin/env python3
"""Create MCPB (MCP Bundle) packages from FastMCP servers.

This script packages FastMCP servers into distributable .mcpb files with
proper manifest generation, dependency handling, and file inclusion.

Usage:
    python create_mcpb.py server.py [options]

Examples:
    # Basic usage
    python create_mcpb.py server.py

    # With custom metadata
    python create_mcpb.py server.py \\
        --name my-server \\
        --version 2.0.0 \\
        --description "API integration server"

    # With dependencies
    python create_mcpb.py server.py \\
        --with requests \\
        --with pydantic>=2.0.0

    # Complete example
    python create_mcpb.py server.py \\
        --name jira-integration \\
        --version 1.0.0 \\
        --author "Your Name <email@example.com>" \\
        --license MIT \\
        --with atlassian-python-api>=3.41.0 \\
        --env JIRA_URL \\
        --env JIRA_PAT \\
        --include assets/ \\
        --include LICENSE
"""

import argparse
import json
import zipfile
from pathlib import Path
from typing import List, Dict, Any
import sys
import re

def extract_server_name(server_path: Path) -> str:
    """Extract server name from Python file."""
    content = server_path.read_text()
    
    # Try to find FastMCP(name="...") pattern
    match = re.search(r'FastMCP\s*\(\s*name\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    
    # Fallback to filename
    return server_path.stem.replace('_', '-')

def extract_dependencies(requirements_file: Path) -> List[str]:
    """Extract dependencies from requirements.txt."""
    if not requirements_file.exists():
        return []
    
    deps = []
    for line in requirements_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            deps.append(line)
    return deps

def create_manifest(
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
) -> Dict[str, Any]:
    """Create MCPB manifest dictionary."""
    
    server_name = name or extract_server_name(server_path)
    
    # Build args for uv command
    args = ["run"]
    
    # Always include fastmcp
    args.extend(["--with", "fastmcp>=2.0.0,<3.0.0"])
    
    # Add other dependencies
    if dependencies:
        for dep in dependencies:
            args.extend(["--with", dep])
    
    # Add entry point
    args.extend(["--", server_path.name])
    
    # Build manifest
    manifest = {
        "manifest_version": "0.1",
        "name": server_name,
        "version": version,
        "server": {
            "type": "python",
            "entry_point": server_path.name,
            "mcp_config": {
                "command": "uv",
                "args": args,
            }
        }
    }
    
    # Add optional fields
    if description:
        manifest["description"] = description
    
    if author:
        manifest["author"] = author
    
    if license:
        manifest["license"] = license
    
    if homepage:
        manifest["homepage"] = homepage
    
    # Add environment variables
    if env_vars:
        manifest["server"]["mcp_config"]["env"] = {var: "" for var in env_vars}
    
    # Add metadata
    if tags:
        manifest["metadata"] = {"tags": tags}
    
    return manifest

def create_bundle(
    server_path: Path,
    output_path: Path,
    manifest: Dict[str, Any],
    include_files: List[str] | None = None,
    exclude_patterns: List[str] | None = None,
) -> None:
    """Create MCPB bundle ZIP file."""
    
    # Default exclusions
    default_excludes = [
        '__pycache__',
        '*.pyc',
        '.pytest_cache',
        '.venv',
        'venv',
        '.git',
        '.vscode',
        '.idea',
        '*.swp',
        '.DS_Store',
        'node_modules',
    ]
    
    exclude_patterns = (exclude_patterns or []) + default_excludes
    
    def should_exclude(path: Path) -> bool:
        """Check if path matches exclusion patterns."""
        import fnmatch
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(str(path), f"*{pattern}*"):
                return True
        return False
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add manifest
        zf.writestr('mcpb.json', json.dumps(manifest, indent=2))
        
        # Add server file
        zf.write(server_path, server_path.name)
        
        # Add requirements.txt if exists
        req_file = server_path.parent / 'requirements.txt'
        if req_file.exists():
            zf.write(req_file, 'requirements.txt')
        
        # Add README if exists
        readme = server_path.parent / 'README.md'
        if readme.exists():
            zf.write(readme, 'README.md')
        
        # Add LICENSE if exists
        license_file = server_path.parent / 'LICENSE'
        if license_file.exists():
            zf.write(license_file, 'LICENSE')
        
        # Add explicitly included files
        if include_files:
            for pattern in include_files:
                for path in Path.cwd().glob(pattern):
                    if path.is_file() and not should_exclude(path):
                        # Preserve directory structure
                        arcname = str(path.relative_to(Path.cwd()))
                        zf.write(path, arcname)
                    elif path.is_dir():
                        # Add directory recursively
                        for subpath in path.rglob('*'):
                            if subpath.is_file() and not should_exclude(subpath):
                                arcname = str(subpath.relative_to(Path.cwd()))
                                zf.write(subpath, arcname)

def validate_bundle(bundle_path: Path) -> bool:
    """Validate MCPB bundle structure."""
    try:
        with zipfile.ZipFile(bundle_path) as zf:
            names = zf.namelist()
            
            # Check required files
            if 'mcpb.json' not in names:
                print("❌ Missing mcpb.json manifest")
                return False
            
            # Validate manifest
            manifest = json.loads(zf.read('mcpb.json'))
            
            # Required fields
            required = ['manifest_version', 'name', 'version', 'server']
            for field in required:
                if field not in manifest:
                    print(f"❌ Manifest missing required field: {field}")
                    return False
            
            # Check entry point exists
            entry = manifest['server']['entry_point']
            if entry not in names:
                print(f"❌ Entry point not in bundle: {entry}")
                return False
            
            print("✓ Bundle is valid")
            return True
            
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as e:
        print(f"❌ Validation failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Create MCPB bundles from FastMCP servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Required arguments
    parser.add_argument(
        'server',
        type=Path,
        help='Path to FastMCP server Python file'
    )
    
    # Optional metadata
    parser.add_argument(
        '--name',
        help='Package name (default: extracted from server file)'
    )
    parser.add_argument(
        '--version',
        default='1.0.0',
        help='Package version (default: 1.0.0)'
    )
    parser.add_argument(
        '--description',
        help='Package description'
    )
    parser.add_argument(
        '--author',
        help='Author name and email (e.g., "Name <email@example.com>")'
    )
    parser.add_argument(
        '--license',
        default='MIT',
        help='License identifier (default: MIT)'
    )
    parser.add_argument(
        '--homepage',
        help='Homepage URL'
    )
    
    # Dependencies
    parser.add_argument(
        '--with',
        dest='dependencies',
        action='append',
        default=[],
        help='Additional dependency (can be used multiple times)'
    )
    parser.add_argument(
        '--requirements',
        type=Path,
        default=Path('requirements.txt'),
        help='Path to requirements.txt (default: ./requirements.txt)'
    )
    
    # Environment
    parser.add_argument(
        '--env',
        dest='env_vars',
        action='append',
        default=[],
        help='Environment variable name (can be used multiple times)'
    )
    
    # File inclusion
    parser.add_argument(
        '--include',
        dest='include_files',
        action='append',
        default=[],
        help='Additional files/directories to include (can be used multiple times)'
    )
    parser.add_argument(
        '--exclude',
        dest='exclude_patterns',
        action='append',
        default=[],
        help='File patterns to exclude (can be used multiple times)'
    )
    
    # Tags
    parser.add_argument(
        '--tag',
        dest='tags',
        action='append',
        default=[],
        help='Package tags (can be used multiple times)'
    )
    
    # Output
    parser.add_argument(
        '--output',
        '-o',
        type=Path,
        help='Output path (default: <name>.mcpb)'
    )
    
    # Validation
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip bundle validation'
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not args.server.exists():
        print(f"❌ Server file not found: {args.server}")
        sys.exit(1)
    
    # Extract dependencies from requirements.txt
    deps_from_file = extract_dependencies(args.requirements) if args.requirements.exists() else []
    all_deps = args.dependencies + deps_from_file
    
    # Create manifest
    manifest = create_manifest(
        server_path=args.server,
        name=args.name,
        version=args.version,
        description=args.description,
        author=args.author,
        license=args.license,
        homepage=args.homepage,
        dependencies=all_deps,
        env_vars=args.env_vars if args.env_vars else None,
        tags=args.tags if args.tags else None,
    )
    
    # Determine output path
    output_path = args.output or Path(f"{manifest['name']}.mcpb")
    
    # Create bundle
    print(f"Creating bundle: {output_path}")
    print(f"  Server: {args.server}")
    print(f"  Name: {manifest['name']}")
    print(f"  Version: {manifest['version']}")
    if all_deps:
        print(f"  Dependencies: {', '.join(all_deps)}")
    if args.env_vars:
        print(f"  Environment: {', '.join(args.env_vars)}")
    
    create_bundle(
        server_path=args.server,
        output_path=output_path,
        manifest=manifest,
        include_files=args.include_files if args.include_files else None,
        exclude_patterns=args.exclude_patterns if args.exclude_patterns else None,
    )
    
    print(f"✓ Bundle created: {output_path}")
    
    # Validate bundle
    if not args.no_validate:
        print("\nValidating bundle...")
        if not validate_bundle(output_path):
            sys.exit(1)
    
    # Show manifest
    print("\nManifest:")
    print(json.dumps(manifest, indent=2))
    
    print(f"\n✓ Successfully created {output_path}")
    print(f"\nInstall with:")
    print(f"  fastmcp install claude-desktop {output_path}")

if __name__ == '__main__':
    main()
