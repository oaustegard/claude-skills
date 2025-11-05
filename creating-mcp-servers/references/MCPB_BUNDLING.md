# MCPB Bundling Guide

## ⚠️ CRITICAL: Use Simple Zip Method

**MCPB is just a ZIP archive with `.mcpb` extension.**

```bash
# Create manifest.json (see format below)
# Then bundle:
cd /home/claude
zip -r server-name.mcpb manifest.json server.py README.md
cp server-name.mcpb /mnt/user-data/outputs/
```

**DO NOT use `mcpb pack` CLI:**
- Requires npm install (breaks on container reset)
- Causes container crashes
- Completely unnecessary

**3 commands. That's it. Don't overcomplicate.**

---

## Overview

MCPB (MCP Bundle) is a packaging format for distributing MCP servers with their dependencies, configuration, and assets in a single file.

## MCPB Format Specification

### Bundle Structure

```
server-name.mcpb (ZIP archive)
├── manifest.json             # Manifest (required)
├── server.py                 # Entry point
├── requirements.txt          # Python dependencies (optional)
├── README.md                 # Documentation (optional)
├── LICENSE                   # License file (optional)
├── assets/                   # Additional files (optional)
│   ├── schemas/
│   └── templates/
└── .mcpignore               # Exclusion patterns (optional)
```

### Manifest Format (manifest.json)

```json
{
    "manifest_version": "0.1",
    "name": "server-name",
    "version": "1.0.0",
    "description": "Server description",
    "author": "Your Name <email@example.com>",
    "license": "MIT",
    "homepage": "https://github.com/user/server",
    "server": {
        "type": "python",
        "entry_point": "server.py",
        "mcp_config": {
            "command": "uv",
            "args": [
                "run",
                "--with",
                "fastmcp>=2.0.0",
                "--with",
                "other-package>=1.0.0",
                "--",
                "server.py"
            ],
            "env": {
                "VARIABLE_NAME": ""
            }
        }
    },
    "metadata": {
        "tags": ["api", "integration"],
        "categories": ["productivity", "development"]
    }
}
```

### Field Descriptions

**Top-level fields:**
- `manifest_version`: MCPB spec version (currently "0.1")
- `name`: Package identifier (lowercase, hyphens, no spaces)
- `version`: Semantic version (MAJOR.MINOR.PATCH)
- `description`: One-line description of functionality
- `author`: Name and email of maintainer
- `license`: SPDX license identifier or "Proprietary"
- `homepage`: URL to documentation or repository

**Server configuration:**
- `type`: Runtime type ("python" or "node")
- `entry_point`: Main server file relative to bundle root
- `mcp_config.command`: Executable to run server ("uv" for Python, "node" for Node)
- `mcp_config.args`: Command-line arguments array
- `mcp_config.env`: Environment variables (values empty = user must provide)

**Metadata (optional):**
- `tags`: Keywords for search/discovery
- `categories`: Classification for organizing servers

---

## Creating MCPB Bundles

### Simple Method (RECOMMENDED)

**This is all you need:**

```bash
# 1. Create manifest.json (see format above)
cat > manifest.json << 'EOF'
{
    "manifest_version": "0.1",
    "name": "my-server",
    "version": "1.0.0",
    "description": "Brief server description",
    "server": {
        "type": "python",
        "entry_point": "server.py",
        "mcp_config": {
            "command": "uv",
            "args": ["run", "--with", "fastmcp>=2.0.0", "--", "server.py"]
        }
    }
}
EOF

# 2. Create ZIP with .mcpb extension
zip -r my-server.mcpb \
    manifest.json \
    server.py \
    README.md

# 3. Move to outputs for user download
cp my-server.mcpb /mnt/user-data/outputs/
```

**That's it. Done.**

To add dependencies, just add more `--with` args in manifest.json:
```json
"args": [
    "run",
    "--with", "fastmcp>=2.0.0",
    "--with", "requests>=2.31.0",
    "--with", "pydantic>=2.0.0",
    "--", "server.py"
]
```

### Optional: Python Script for Complex Cases

For automation or complex dependency handling, use `scripts/create_mcpb.py`:

```bash
# Basic usage
python scripts/create_mcpb.py server.py

# With dependencies and metadata
python scripts/create_mcpb.py server.py \
    --name jira-datacenter \
    --version 1.0.0 \
    --description "Read-only Jira DataCenter integration" \
    --with atlassian-python-api>=3.41.0 \
    --env JIRA_URL \
    --env JIRA_PAT
```

**Only use the script if you need:**
- Automated builds in CI/CD
- Complex multi-file inclusion patterns
- Dependency detection from requirements.txt

---

## Installing MCPB Bundles

### Claude Desktop Installation

```bash
# Method 1: Via fastmcp CLI
fastmcp install claude-desktop path/to/server.mcpb

# Method 2: Extract and configure manually
unzip server.mcpb -d ~/.claude/mcp-servers/server-name
# Then add to claude_desktop_config.json
```

### Claude Code Installation

```bash
# Install bundle
fastmcp install claude-code path/to/server.mcpb

# Verify installation
claude-code mcp list
```

### Manual Installation

```bash
# 1. Extract bundle
mkdir -p ~/mcp-servers/server-name
unzip server.mcpb -d ~/mcp-servers/server-name

# 2. Read manifest.json and add to MCP client config
# Example for Claude Desktop:
{
    "mcpServers": {
        "server-name": {
            "command": "uv",
            "args": [
                "run",
                "--with", "fastmcp>=2.0.0",
                "--", "~/mcp-servers/server-name/server.py"
            ],
            "env": {
                "VARIABLE": "value"
            }
        }
    }
}
```

---

## Best Practices

### Manifest Design

```json
{
    "manifest_version": "0.1",
    "name": "my-server",
    "version": "1.0.0",
    
    // ✅ Good: Concise, informative description
    "description": "GitHub API integration with progressive disclosure",
    
    // ❌ Bad: Vague or overly verbose
    // "description": "A server that does things with GitHub maybe"
    
    // ✅ Good: Include contact info
    "author": "Your Name <email@example.com>",
    
    // ✅ Good: Pin FastMCP version
    "mcp_config": {
        "args": ["run", "--with", "fastmcp>=2.0.0,<3.0.0", ...]
    },
    
    // ❌ Bad: Unpinned versions
    // "args": ["run", "--with", "fastmcp", ...]
}
```

### Dependency Management

```bash
# ✅ Good: Pin major versions, allow minor updates
uv pip install 'fastmcp>=2.0.0,<3.0.0'
uv pip install 'requests>=2.31.0,<3.0.0'

# ✅ Good: Use requirements.txt for complex deps
cat requirements.txt
fastmcp>=2.0.0,<3.0.0
requests>=2.31.0,<3.0.0
pydantic>=2.0.0,<3.0.0

# ❌ Bad: Unpinned or overly strict
fastmcp  # Any version
fastmcp==2.0.0  # Too strict
```

### File Inclusion

```python
# .mcpignore pattern (gitignore syntax)
# Exclude development files
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/

# Exclude IDE files
.vscode/
.idea/
*.swp

# Exclude Git
.git/
.gitignore

# Exclude documentation source
docs/source/
*.md~

# Include only what's needed for runtime
!README.md
!LICENSE
```

### Security Considerations

```json
{
    // ✅ Good: Environment variables for secrets
    "env": {
        "API_KEY": "",  // User provides
        "API_URL": ""   // User provides
    },
    
    // ❌ Bad: Hardcoded secrets
    // "env": {
    //     "API_KEY": "sk-abc123..."
    // }
    
    // ✅ Good: Document required environment variables
    "description": "Requires API_KEY and API_URL environment variables"
}
```

---

## Distribution

### Publishing to GitHub

```bash
# 1. Create bundle
python scripts/create_mcpb.py server.py

# 2. Create GitHub release
gh release create v1.0.0 \
    server-name.mcpb \
    --title "Release v1.0.0" \
    --notes "Initial release"

# 3. Users download and install
wget https://github.com/user/repo/releases/download/v1.0.0/server-name.mcpb
fastmcp install claude-desktop server-name.mcpb
```

### Bundle Registry (Future)

```bash
# Planned MCP Bundle Registry
fastmcp search github
fastmcp install github-integration
fastmcp update github-integration
```

---

## Validation

### Pre-Bundle Validation

```bash
# Check manifest
python -m json.tool manifest.json

# Verify entry point exists
test -f server.py && echo "✓ Entry point found"

# Check dependencies
uv pip compile requirements.txt

# Test server locally
uv run --with fastmcp server.py
```

### Post-Bundle Validation

```bash
# Verify ZIP structure
unzip -l server-name.mcpb

# Extract and test
unzip -d /tmp/test server-name.mcpb
cd /tmp/test
uv run --with fastmcp server.py
```

### Automated Validation Script

```python
#!/usr/bin/env python3
"""Validate MCPB bundle structure and manifest."""

import json
import zipfile
import sys
from pathlib import Path

def validate_mcpb(bundle_path: Path) -> bool:
    """Validate MCPB bundle."""
    errors = []
    
    # Check ZIP format
    if not zipfile.is_zipfile(bundle_path):
        errors.append("Not a valid ZIP file")
        return False
    
    with zipfile.ZipFile(bundle_path) as zf:
        names = zf.namelist()
        
        # Check required files
        if 'manifest.json' not in names:
            errors.append("Missing manifest.json")
        
        # Validate manifest
        try:
            manifest = json.loads(zf.read('manifest.json'))
            
            # Required fields
            required = ['manifest_version', 'name', 'version', 'server']
            for field in required:
                if field not in manifest:
                    errors.append(f"Manifest missing required field: {field}")
            
            # Check entry point exists
            entry = manifest['server']['entry_point']
            if entry not in names:
                errors.append(f"Entry point not in bundle: {entry}")
            
        except json.JSONDecodeError as e:
            errors.append(f"Invalid manifest JSON: {e}")
    
    # Report
    if errors:
        print("❌ Validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("✓ Bundle is valid")
        return True

if __name__ == "__main__":
    sys.exit(0 if validate_mcpb(Path(sys.argv[1])) else 1)
```

---

## Common Patterns

### Pattern 1: Single-File Server

```
simple-server.mcpb
├── manifest.json
└── server.py
```

**Manifest:**
```json
{
    "manifest_version": "0.1",
    "name": "simple-server",
    "version": "1.0.0",
    "server": {
        "type": "python",
        "entry_point": "server.py",
        "mcp_config": {
            "command": "uv",
            "args": ["run", "--with", "fastmcp>=2.0.0", "--", "server.py"]
        }
    }
}
```

### Pattern 2: Multi-File Server with Assets

```
complex-server.mcpb
├── manifest.json
├── server.py
├── requirements.txt
├── README.md
├── LICENSE
└── assets/
    ├── schemas/
    │   └── api_schema.json
    └── templates/
        └── response.j2
```

**Manifest:**
```json
{
    "manifest_version": "0.1",
    "name": "complex-server",
    "version": "1.0.0",
    "description": "Advanced server with schemas and templates",
    "server": {
        "type": "python",
        "entry_point": "server.py",
        "mcp_config": {
            "command": "uv",
            "args": [
                "run",
                "--with", "fastmcp>=2.0.0",
                "--with", "jinja2>=3.1.0",
                "--", "server.py"
            ]
        }
    }
}
```

### Pattern 3: Environment-Configured Server

```json
{
    "manifest_version": "0.1",
    "name": "api-server",
    "version": "1.0.0",
    "description": "API integration (requires API_KEY and API_URL)",
    "server": {
        "type": "python",
        "entry_point": "server.py",
        "mcp_config": {
            "command": "uv",
            "args": [
                "run",
                "--with", "fastmcp>=2.0.0",
                "--with", "requests>=2.31.0",
                "--", "server.py"
            ],
            "env": {
                "API_KEY": "",
                "API_URL": "",
                "DEBUG": "false"
            }
        }
    }
}
```

---

## Troubleshooting

### Common Issues

**Issue: Bundle extraction fails**
```bash
# Check ZIP integrity
unzip -t server.mcpb

# Try manual extraction
mkdir test && cd test
unzip ../server.mcpb
```

**Issue: Server won't start**
```bash
# Check dependencies
uv pip list
uv pip install -r requirements.txt

# Test entry point directly
uv run --with fastmcp server.py

# Check Python version
python --version  # Should be 3.9+
```

**Issue: Environment variables not set**
```bash
# Check manifest
jq '.server.mcp_config.env' manifest.json

# Set variables before running
export API_KEY="your-key"
export API_URL="https://api.example.com"
fastmcp install claude-desktop server.mcpb
```

### Debug Mode

```json
{
    "mcp_config": {
        "command": "uv",
        "args": [...],
        "env": {
            "DEBUG": "true",
            "LOG_LEVEL": "debug"
        }
    }
}
```

---

## Migration Guide

### Converting Existing Server to MCPB

```bash
# 1. Ensure uv usage
# Update all pip → uv in docs/scripts

# 2. Create manifest
python scripts/create_mcpb.py server.py \
    --name existing-server \
    --version 1.0.0 \
    --with $(cat requirements.txt | tr '\n' ' ')

# 3. Test bundle
fastmcp install claude-desktop existing-server.mcpb
# Verify functionality

# 4. Distribute
gh release create v1.0.0 existing-server.mcpb
```

---

## Appendix: Complete Example

**File: server.py**
```python
from fastmcp import FastMCP
from typing import Annotated
from pydantic import Field

mcp = FastMCP(
    name="example-server",
    instructions="Example MCP server for MCPB demonstration."
)

@mcp.tool(annotations={"title": "Echo", "readOnlyHint": True})
async def echo(
    message: Annotated[str, Field(description="Message to echo")]
) -> str:
    """Echo message back. Simple demonstration tool."""
    return f"Echo: {message}"
```

**File: requirements.txt**
```
fastmcp>=2.0.0,<3.0.0
```

**File: manifest.json**
```json
{
    "manifest_version": "0.1",
    "name": "example-server",
    "version": "1.0.0",
    "description": "Example MCP server demonstrating MCPB format",
    "author": "Your Name <email@example.com>",
    "license": "MIT",
    "server": {
        "type": "python",
        "entry_point": "server.py",
        "mcp_config": {
            "command": "uv",
            "args": [
                "run",
                "--with", "fastmcp>=2.0.0,<3.0.0",
                "--", "server.py"
            ]
        }
    }
}
```

**Create Bundle:**
```bash
zip -r example-server.mcpb \
    manifest.json \
    server.py \
    requirements.txt

# Or use script
python scripts/create_mcpb.py server.py \
    --name example-server \
    --version 1.0.0
```

**Install:**
```bash
fastmcp install claude-desktop example-server.mcpb
```

---

## Further Reading

- FastMCP Documentation: https://gofastmcp.com
- MCPB Specification: https://github.com/anthropics/mcpb
- Package Distribution: ./DISTRIBUTION.md
- Claude Desktop Integration: https://gofastmcp.com/integrations/claude-desktop.md
