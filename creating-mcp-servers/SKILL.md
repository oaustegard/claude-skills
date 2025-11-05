---
name: creating-mcp-servers
description: Creates production-ready MCP servers using FastMCP v2. Use when building MCP servers, optimizing tool descriptions for context efficiency, implementing progressive disclosure for multiple capabilities, or packaging servers for distribution.
---

# Creating MCP Servers

Build production-ready MCP servers using FastMCP v2 with optimal context efficiency through progressive disclosure patterns.

## Core Capabilities

1. **Apply mandatory patterns** - Four critical requirements for consistency
2. **Implement progressive disclosure** - Gateway patterns achieving 85-93% token reduction  
3. **Optimize tool descriptions** - 65-70% token reduction through proper patterns
4. **Bundle servers** - Package as MCPB files with validation
5. **Proven gateway patterns** - Three complete implementations (Skills, API, Query)

## When to Use

**Trigger phrases:**
- "MCP server", "create MCP", "build MCP", "FastMCP"
- "progressive disclosure", "gateway pattern", "context efficient"
- "optimize MCP", "reduce context", "tool descriptions"
- "MCPB", "bundle MCP", "package server"

**Use for:**
- Creating new MCP servers with FastMCP v2
- Optimizing existing tool descriptions
- Implementing progressive disclosure for 5+ capabilities
- Converting Skills to MCP or vice versa
- Packaging servers for distribution

## Architecture Decision

```
1-3 simple tools?
  → Standard FastMCP with optimized tools
  Load: references/MANDATORY_PATTERNS.md

5+ related capabilities?
  → Gateway pattern (progressive disclosure)
  Load: references/PROGRESSIVE_DISCLOSURE.md
  Load: references/GATEWAY_PATTERNS.md

Optimize existing server?
  → Apply mandatory patterns
  Load: references/MANDATORY_PATTERNS.md

Package for distribution?
  → MCPB bundler
  Load: references/MCPB_BUNDLING.md
  Execute: scripts/create_mcpb.py

Need FastMCP documentation?
  → Search references/FASTMCP_DOCS.md for relevant URLs
  → Use web_fetch on gofastmcp.com URLs
```

## Mandatory Patterns

Four critical requirements for ALL implementations:

1. **uv (never pip)** - Dependency management consistency
2. **Optimized tool descriptions** - Annotations, Annotated, concise docstrings
3. **Authoritative documentation** - Fetch from gofastmcp.com (see workflow below)
4. **Strategic tool selection** - Best tool for each job

Details in [references/MANDATORY_PATTERNS.md](references/MANDATORY_PATTERNS.md)

## Progressive Disclosure Pattern

For servers with 5+ capabilities:

**Three-tier loading:**
1. Metadata (~20 tokens/capability) - Always loaded
2. Content (~500 tokens) - Load on demand
3. Execution (0 tokens) - Execute without loading

Achieves 85-93% baseline reduction. See [references/PROGRESSIVE_DISCLOSURE.md](references/PROGRESSIVE_DISCLOSURE.md)

## Implementation Workflow

### Phase 1: Research FastMCP Patterns

**IMPORTANT:** Claude fetches documentation, not scripts (skill environment has restricted network access).

**Workflow:**
```
1. Read references/FASTMCP_DOCS.md - comprehensive URL index
2. Identify relevant documentation URLs for your task
3. Use web_fetch on gofastmcp.com URLs (Claude has network access)
4. Apply patterns from fetched documentation
```

**Example searches:**
- Authentication patterns → Search FASTMCP_DOCS.md for "authentication"
- Tool optimization → Search for "tools" 
- OAuth flows → Search for "oauth"
- Deployment → Search for "deployment"

**URL format:** All docs at `https://gofastmcp.com/[path].md`

### Phase 2: Implement Server

Load appropriate reference based on architecture decision above.

**For standard servers:**
- Apply all four mandatory patterns
- Optimize tool descriptions (annotations, Annotated, Field)
- Single-sentence docstrings with high information density

**For gateway servers:**
- Implement three-tier loading (discover, load, execute)
- Use proven patterns from GATEWAY_PATTERNS.md
- Validate 85%+ context reduction

### Phase 3: Package (Optional)

**Simple zip bundling:**

```bash
# 1. Create manifest.json (see MCPB_BUNDLING.md for format)
# 2. Bundle with zip
cd /home/claude
zip -r server-name.mcpb manifest.json server.py README.md
cp server-name.mcpb /mnt/user-data/outputs/

# Or for automated builds:
python scripts/create_mcpb.py server.py --name server-name --version 1.0.0
```

See [references/MCPB_BUNDLING.md](references/MCPB_BUNDLING.md) for manifest format and details.

## Reference Library

Load as needed during development:

**Documentation index:**
- [FASTMCP_DOCS.md](references/FASTMCP_DOCS.md) - Complete FastMCP v2 documentation URLs (Claude fetches via web_fetch)

**Core patterns (load first):**
- [MANDATORY_PATTERNS.md](references/MANDATORY_PATTERNS.md) - Four critical requirements
- [PROGRESSIVE_DISCLOSURE.md](references/PROGRESSIVE_DISCLOSURE.md) - Architecture for 5+ capabilities

**Implementation:**
- [GATEWAY_PATTERNS.md](references/GATEWAY_PATTERNS.md) - Three production-ready implementations
- [MCPB_BUNDLING.md](references/MCPB_BUNDLING.md) - Packaging and distribution

**Scripts (execute as needed):**
- `scripts/create_mcpb.py` - Bundle MCP servers into .mcpb files

## Network Access Note

**Skill environment:** Restricted network (package repos only)  
**Claude (using skill):** Full network access via web_fetch

**This means:**
- Scripts cannot fetch URLs
- Claude must use web_fetch for gofastmcp.com documentation
- FASTMCP_DOCS.md provides URL index for Claude to fetch

## Verification Checklist

Before completing any FastMCP implementation:

```
✓ Uses uv (not pip)
✓ FastMCP docs fetched from gofastmcp.com (not web_search)
✓ Tool annotations (readOnlyHint, title, openWorldHint)
✓ Annotated parameters with Field
✓ Single-sentence docstrings
✓ 65-70% token reduction vs verbose
✓ Server instructions concise (<100 chars)
✓ Strategic tool usage documented
```

For gateway implementations, additionally verify:
```
✓ 85%+ baseline context reduction
✓ Discover returns metadata only
✓ Load fetches content on demand
✓ Execute runs without context cost
```

## Key Optimization

**Tool description pattern:**

Before (180 tokens):
```
Search for items in the database.
This tool allows comprehensive searching...
```

After (55 tokens):
```python
"""Search items. Fast full-text search."""
# + annotations={"title": "Search", "readOnlyHint": True}
# + Annotated parameters with Field
```

## Common Pitfalls

❌ Using `mcpb pack` CLI (causes crashes, just use `zip`)  
❌ Using pip instead of uv  
❌ web_search for FastMCP docs (use web_fetch on gofastmcp.com)  
❌ Verbose tool descriptions  
❌ Missing tool annotations  
❌ Gateway for 1-3 tools (overhead exceeds benefit)  
❌ Mixing unrelated capabilities in single gateway  
❌ Scripts trying to fetch URLs (network restricted)

## Expected Results

**Context efficiency:**
- 85-93% baseline reduction (gateway pattern)
- 65-70% tool description reduction (optimization)
- 0 tokens for script execution (progressive disclosure)

**Quality:**
- Production-ready immediately
- All mandatory patterns applied
- Security and error handling included
- Strategic tool usage documented
