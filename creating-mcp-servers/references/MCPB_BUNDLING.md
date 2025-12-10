# MCPB Bundling Guide

## Simple Method (Use This)

**MCPB is just a ZIP archive with `.mcpb` extension.**

```bash
# 1. Create manifest.json (see format below)
# 2. Bundle with zip
cd /home/claude
zip -r server-name.mcpb manifest.json server.py README.md
cp server-name.mcpb /mnt/user-data/outputs/
```

**DO NOT use `mcpb pack` CLI** - causes container crashes.

---

## Bundle Structure

```
server-name.mcpb (ZIP archive)
├── manifest.json             # Required
├── server.py                 # Entry point
├── requirements.txt          # Optional
├── README.md                 # Optional
└── assets/                   # Optional
```

---

## Manifest Format

```json
{
    "manifest_version": "0.1",
    "name": "server-name",
    "version": "1.0.0",
    "description": "Server description",
    "author": "Your Name <email@example.com>",
    "license": "MIT",
    "server": {
        "type": "python",
        "entry_point": "server.py",
        "mcp_config": {
            "command": "uv",
            "args": [
                "run",
                "--with", "fastmcp>=2.0.0",
                "--with", "other-package>=1.0.0",
                "--", "server.py"
            ],
            "env": {
                "API_KEY": "",
                "API_URL": ""
            }
        }
    }
}
```

### Field Descriptions

**Top-level:**
- `manifest_version`: MCPB spec version ("0.1")
- `name`: Package identifier (lowercase, hyphens, no spaces)
- `version`: Semantic version (MAJOR.MINOR.PATCH)
- `description`: One-line description
- `author`: Name and email
- `license`: SPDX identifier or "Proprietary"

**Server configuration:**
- `type`: "python" or "node"
- `entry_point`: Main server file
- `mcp_config.command`: Executable ("uv" for Python)
- `mcp_config.args`: Command-line arguments
- `mcp_config.env`: Environment variables (empty = user must provide)

---

## Creating Bundles

### Minimal Bundle

```bash
# Create manifest
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

# Create ZIP
zip -r my-server.mcpb manifest.json server.py README.md

# Move to outputs
cp my-server.mcpb /mnt/user-data/outputs/
```

### With Dependencies

```json
"args": [
    "run",
    "--with", "fastmcp>=2.0.0",
    "--with", "requests>=2.31.0",
    "--with", "pydantic>=2.0.0",
    "--", "server.py"
]
```

### With Environment Variables

```json
"mcp_config": {
    "command": "uv",
    "args": ["run", "--with", "fastmcp>=2.0.0", "--", "server.py"],
    "env": {
        "API_KEY": "",
        "API_URL": "",
        "DEBUG": "false"
    }
}
```

---

## Installing Bundles

### Claude Desktop
```bash
fastmcp install claude-desktop server.mcpb
```

### Claude Code
```bash
fastmcp install claude-code server.mcpb
```

### Manual
```bash
mkdir -p ~/mcp-servers/server-name
unzip server.mcpb -d ~/mcp-servers/server-name
# Add to MCP client config from manifest.json
```

---

## Validation

```bash
# Check ZIP structure
unzip -l server.mcpb

# Extract and test
unzip -d /tmp/test server.mcpb
cd /tmp/test
uv run --with fastmcp server.py
```

---

## Common Patterns

### Single-File Server
```
simple-server.mcpb
├── manifest.json
└── server.py
```

### Multi-File with Assets
```
complex-server.mcpb
├── manifest.json
├── server.py
├── requirements.txt
├── README.md
└── assets/
    └── schemas/
```

### Environment-Configured
```json
{
    "description": "Requires API_KEY and API_URL",
    "server": {
        "mcp_config": {
            "env": {
                "API_KEY": "",
                "API_URL": ""
            }
        }
    }
}
```

---

## Best Practices

**Manifest:**
- Pin FastMCP version: `"fastmcp>=2.0.0,<3.0.0"`
- Document required env vars in description
- Include contact info in author field

**Security:**
- Environment variables for secrets (never hardcode)
- Empty values = user must provide

**Dependencies:**
- Pin major versions, allow minor updates
- Example: `"requests>=2.31.0,<3.0.0"`

---

## Troubleshooting

**Bundle extraction fails:**
```bash
unzip -t server.mcpb  # Check integrity
```

**Server won't start:**
```bash
uv pip list
uv run --with fastmcp server.py
```

**Environment variables not set:**
```bash
export API_KEY="your-key"
export API_URL="https://api.example.com"
fastmcp install claude-desktop server.mcpb
```
