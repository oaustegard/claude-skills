# FastMCP Mandatory Patterns

Four critical requirements for ALL FastMCP implementations.

## 1. Use uv (Never pip)

**Rule:** Always use uv for dependency management.

**Installation:**
```bash
uv pip install fastmcp
uv pip install -r requirements.txt
uv venv
uv sync
fastmcp install claude-desktop server.py --with dependency
```

**Apply to:**
- README installation instructions
- requirements.txt notes (add: "Install with: uv pip install -r requirements.txt")
- Installation scripts
- All code examples and documentation

**Installation Script Pattern:**
```bash
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv pip install -r requirements.txt
```

---

## 2. Fetch FastMCP Docs from Authoritative Sources

**Rule:** For FastMCP knowledge, use LLMS_TXT.md + web_fetch

**Workflow:**
```
1. Read references/LLMS_TXT.md - comprehensive URL index
2. Search LLMS_TXT.md for relevant topic
3. Use web_fetch: https://gofastmcp.com/[path].md
4. Apply authoritative patterns
```

**Common topics:**
- Authentication → Search for "authentication"
- Tool optimization → Search for "tools"
- Client integration → Search for "transports" or client name
- Deployment → Search for "deployment" or "running"
- OAuth flows → Search for "oauth"
- Middleware → Search for "middleware"

**URL Structure:**
- Base: `https://gofastmcp.com/`
- All docs have `.md` extension
- Example: `https://gofastmcp.com/servers/tools.md`

---

## 3. Optimize ALL MCP Tool Descriptions

**Target:** 65-70% token reduction vs. verbose approach

**Verbose (~180 tokens):**
```python
@mcp.tool()
async def search_jql(jql: str, max_results: int = 50):
    """
    Search Jira issues using JQL (Jira Query Language).
    
    This tool allows you to search through all issues...
    
    Args:
        jql: JQL query string...
        max_results: Maximum number of results...
    
    Returns:
        Dictionary with issues, total, maxResults
        
    Example JQL queries:
        - "project = MYPROJ"
        ...
    """
```

**Optimized (~55 tokens):**
```python
@mcp.tool(
    annotations={
        "title": "Search Jira with JQL",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
async def search_jql(
    jql: Annotated[str, Field(
        description="JQL query. Ex: 'project = PROJ', 'status = Open'"
    )],
    max_results: Annotated[int, Field(
        description="Max results (1-100)",
        ge=1,
        le=100
    )] = 50,
    ctx: Context = None
):
    """Search Jira using JQL. Supports projects, status, assignee, dates, sorting."""
```

### Optimization Techniques

**1. Annotations (Metadata Outside Context)**
```python
annotations={
    "title": "Human-Readable Title",    # UI display name
    "readOnlyHint": True,               # Signals no modifications
    "openWorldHint": False,             # Internal system vs external APIs
    "idempotentHint": True,             # Repeated calls safe
    "destructiveHint": False            # Non-destructive operations
}
```

**2. Annotated Parameters with Field**
```python
from typing import Annotated
from pydantic import Field

# Basic pattern
param: Annotated[str, Field(description="Concise description")]

# With validation
count: Annotated[int, Field(
    description="Item count (1-100)",
    ge=1,
    le=100
)] = 10

# With inline examples
query: Annotated[str, Field(
    description="JQL query. Ex: 'project = KEY', 'status = Open'"
)]

# With pattern validation
key: Annotated[str, Field(
    description="Issue key (PROJECT-123)",
    pattern=r'^[A-Z]+-\d+$'
)]
```

**3. Single-Sentence Docstring Pattern**
```
"{Action verb} {scope/target}. {Key capabilities/differentiators}."
```

Examples:
- `"Search Jira using JQL. Supports projects, status, assignee, dates, sorting."`
- `"Retrieve complete issue details. Returns description, comments, attachments, history."`
- `"Add comment to issue. Supports Markdown formatting and @mentions."`

**4. Server-Level Instructions**
```python
mcp = FastMCP(
    name="Service Name",
    instructions="High-level guidance. Key capabilities. Permission/scope info."
)
```

Pattern: Single sentence, <100 characters

Examples:
- `"Read-only Jira access. All operations respect user permissions."`
- `"GitHub repo management. Read/write access."`
- `"Database query interface. Read-only. SQL with parameter escaping."`

**5. Context Efficiency Targets**

| Tool Complexity | Before | After | Reduction |
|-----------------|--------|-------|-----------|
| Simple (list) | 120 | 35 | 71% |
| Medium (search) | 180 | 55 | 69% |
| Complex (multi-param) | 250 | 75 | 70% |

---

## 4. Implementation Checklist

Before delivering any FastMCP implementation:

```
✓ All commands use uv (not pip)
✓ FastMCP docs fetched from LLMS_TXT.md URLs (not web_search)
✓ Tool annotations include readOnlyHint, title, openWorldHint  
✓ Parameters use Annotated[type, Field(description="...")]
✓ Docstrings are single sentence, high-density
✓ Token usage ~65-70% less than verbose approach
✓ Server instructions concise (<100 chars)
✓ No pip references anywhere
✓ Validation constraints in Field (ge, le, pattern)
✓ Error handling specific (ApiError vs generic Exception)
✓ Security measures (input validation, escaping)
```

---

## Quick Decision Tree

```
Starting new FastMCP implementation?
│
├─ Will use uv? (not pip)
│  ├─ Yes → Continue
│  └─ No → Fix this first
│
├─ Need FastMCP docs?
│  ├─ Yes → Use LLMS_TXT.md + web_fetch (not web_search)
│  └─ No → Continue
│
├─ Creating MCP tools?
│  ├─ Yes → Apply optimization patterns
│  │         (annotations, Annotated, concise docstrings)
│  └─ No → Continue
│
└─ Verify all four patterns applied
```

---

## Example: Complete Tool Implementation

```python
from fastmcp import FastMCP, Context
from typing import Annotated
from pydantic import Field

mcp = FastMCP(
    name="example-service",
    instructions="Example integration. Read-only access."
)

@mcp.tool(
    annotations={
        "title": "Search Items",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
async def search_items(
    query: Annotated[str, Field(
        description="Search text. Ex: 'status:active', 'name:test'"
    )],
    limit: Annotated[int, Field(
        description="Max results (1-100)",
        ge=1,
        le=100
    )] = 50,
    ctx: Context = None
) -> dict:
    """Search items by text. Full-text search across all fields."""
    
    # Implementation
    results = await api.search(query, limit=limit)
    return {"items": results, "count": len(results)}
```
