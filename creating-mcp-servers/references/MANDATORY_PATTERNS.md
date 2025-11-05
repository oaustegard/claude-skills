# FastMCP Mandatory Patterns - Complete Reference

## Four Critical Requirements for ALL FastMCP Implementations

These patterns MUST be applied without exception to every FastMCP implementation.

### 1. Use uv (Never pip)

**Rule:** Always use uv for dependency management

**Installation:**
```bash
# ✅ Correct
uv pip install fastmcp
uv pip install -r requirements.txt
uv venv
uv sync
fastmcp install claude-desktop server.py --with dependency
```

**❌ Wrong:**
```bash
pip install fastmcp
pip install -r requirements.txt
python -m venv venv
```

**Why:** FastMCP ecosystem standard, faster, better consistency

**Apply to:**
- README installation instructions
- requirements.txt notes (add: "Install with: uv pip install -r requirements.txt")
- Installation scripts (check for uv, install if missing)
- All code examples and documentation
- CI/CD pipelines

**Installation Script Pattern:**
```bash
# Check for uv and install if needed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv pip install -r requirements.txt
```

---

### 2. Fetch FastMCP Docs from Authoritative Sources (Never web_search)

**Rule:** For FastMCP knowledge, Claude uses FASTMCP_DOCS.md + web_fetch

**IMPORTANT:** Claude fetches documentation (skill scripts cannot - network restricted to package repos).

**✅ Correct workflow:**
```
1. Read references/FASTMCP_DOCS.md - comprehensive URL index
2. Search FASTMCP_DOCS.md for relevant topic
3. Claude uses web_fetch: https://gofastmcp.com/[path].md
4. Apply authoritative patterns
```

**❌ Wrong:**
```python
web_search("FastMCP [topic]")  # Outdated/incomplete/unreliable
```

**Why:** Authoritative, current, complete FastMCP v2 documentation

**Common topics:**
- Authentication patterns → Search FASTMCP_DOCS.md for "authentication"
- Tool optimization → Search for "tools"
- Client integration → Search for "transports" or client name
- Deployment → Search for "deployment" or "running"
- OAuth flows → Search for "oauth"
- Middleware → Search for "middleware"
- Resources → Search for "resources"
- Prompts → Search for "prompts"

**URL Structure:**
- Base: `https://gofastmcp.com/`
- All docs have `.md` extension
- Example: `https://gofastmcp.com/servers/tools.md`

**Decision Matrix:**

| Query Type | Correct Approach | Wrong Approach |
|------------|------------------|----------------|
| FastMCP features | FASTMCP_DOCS.md + web_fetch | web_search |
| FastMCP best practices | FASTMCP_DOCS.md + web_fetch | web_search |
| FastMCP examples | FASTMCP_DOCS.md + web_fetch | web_search |
| General Python | Standard knowledge | N/A |
| Other MCP implementations | web_search | FASTMCP_DOCS.md |

---

### 3. Optimize ALL MCP Tool Descriptions

**Rule:** Apply FastMCP best practices for context efficiency

**Target:** 65-70% token reduction vs. verbose approach

**❌ Verbose (~180 tokens, wastes context):**
```python
@mcp.tool()
async def search_jql(jql: str, max_results: int = 50):
    """
    Search Jira issues using JQL (Jira Query Language).
    
    This tool allows you to search through all issues that you have
    access to based on your permissions. It performs a JQL search
    across the Jira instance.
    
    Args:
        jql: JQL query string (e.g., "project = PROJ AND status = Open")
            The query should use standard JQL syntax. Supports:
            - Project filters: project = KEY
            - Status filters: status = "In Progress"
            - Assignee filters: assignee = currentUser()
            - Date filters: created >= -7d
        max_results: Maximum number of results to return (default: 50, max: 100)
            Controls pagination. Larger values may take longer to process.
    
    Returns:
        Dictionary with:
        - issues: List of issue objects with keys, summaries, statuses
        - total: Total number of matching issues
        - maxResults: Number of results returned
        
    Example JQL queries:
        - "project = MYPROJ"
        - "assignee = currentUser()"
        - "status = Open AND priority = High"
        - "created >= -30d ORDER BY created DESC"
    
    Raises:
        ValueError: If JQL syntax is invalid
        ToolError: If Jira API returns an error
    """
```

**✅ Optimized (~55 tokens, 69% reduction):**
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
        description="JQL query. Ex: 'project = PROJ', 'status = Open', 'assignee = currentUser()'"
    )],
    max_results: Annotated[int, Field(
        description="Max results (1-100)",
        ge=1,
        le=100
    )] = 50,
    ctx: Context = None
):
    """Search Jira using JQL. Most powerful search - supports projects, status, assignee, dates, sorting."""
```

**Optimization Techniques:**

#### 1. Annotations (Metadata Outside Context)
```python
annotations={
    "title": "Human-Readable Title",  # UI display name
    "readOnlyHint": True,              # Signals no modifications (REQUIRED for read ops)
    "openWorldHint": False,            # Internal system vs external APIs
    "idempotentHint": True,            # Repeated calls safe
    "destructiveHint": False           # Non-destructive operations
}
```

#### 2. Annotated Parameters with Field
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

#### 3. Single-Sentence Docstring Pattern
```
"{Action verb} {scope/target}. {Key capabilities/differentiators}."
```

**Examples:**
- `"Search Jira using JQL. Most powerful search - supports projects, status, assignee, dates, sorting."`
- `"Retrieve complete issue details. Returns description, comments, attachments, history, transitions."`
- `"List user's assigned issues. Filtered by current user, sorted by priority."`
- `"Add comment to issue. Supports Markdown formatting and @mentions."`

**What to NEVER include in docstrings:**
- Parameter descriptions (use Annotated instead)
- Return value details (inferred from type hints)
- Examples (use Field description for inline examples)
- Raised exceptions (handle with try/except)
- Long-form explanations (use concise, high-density language)

#### 4. Server-Level Instructions
```python
mcp = FastMCP(
    name="Service Name",
    instructions="High-level guidance. Key capabilities. Permission/scope info."
)
```

**Pattern:** Single sentence, <100 characters

**Examples:**
- `"Read-only Jira access. All operations respect user permissions. Use JQL for complex searches."`
- `"GitHub repo management. Read/write access. Use search for discovery, webhooks for automation."`
- `"Database query interface. Read-only. Supports SQL with automatic parameter escaping."`

#### 5. Context Efficiency Targets

| Tool Complexity | Before | After | Reduction |
|-----------------|--------|-------|-----------|
| Simple (list) | 120 | 35 | 71% |
| Medium (search) | 180 | 55 | 69% |
| Complex (multi-param) | 250 | 75 | 70% |
| **Overall Server** | **1200** | **380** | **68%** |

---

### 4. Check Available Tools First

**Rule:** Analyze available tools before choosing implementation approach

**✅ Strategic tool selection:**
```python
Query: "Create FastMCP server for GitHub integration"

Analysis:
1. FastMCP patterns needed → llms.txt + web_fetch
2. GitHub repo understanding → DeepWiki (if available)
3. General research → web_search (fallback only)

Implementation:
- Load FastMCP docs from llms.txt URLs
- Use DeepWiki to understand GitHub API patterns
- web_search only for gaps
```

**❌ Reactive approach:**
```python
Query: "Create FastMCP server for GitHub integration"

→ Immediately web_search without checking for better tools
→ Miss authoritative FastMCP docs
→ Miss GitHub-specific DeepWiki analysis
```

**Decision Framework:**

| Query Type | Tool Priority | Rationale |
|------------|---------------|-----------|
| FastMCP patterns | llms.txt + web_fetch | Authoritative docs |
| GitHub repo structure | DeepWiki:read_wiki_structure | Comprehensive analysis |
| GitHub repo docs | DeepWiki:read_wiki_contents | Detailed documentation |
| Specific GitHub questions | DeepWiki:ask_question | Targeted answers |
| General web research | web_search | Fallback only |
| Past conversations | conversation_search | Context continuity |
| Recent user activity | recent_chats | Session awareness |

**Tool Capability Matrix:**

```
Available Tools:
├─ Documentation Access
│  ├─ llms.txt (FastMCP) → Authoritative, current
│  └─ DeepWiki (Repos) → Comprehensive, indexed
├─ Search
│  ├─ web_search → General internet
│  ├─ conversation_search → Past chats
│  └─ recent_chats → Session history
├─ Code Analysis
│  └─ DeepWiki → Repo structure, docs, questions
└─ Content Fetch
   └─ web_fetch → Specific URLs
```

**Before Implementation Checklist:**

```
Before implementing ANY FastMCP solution:

□ Identify query requirements
□ List available tools in function schema
□ Map requirements to tool capabilities
□ Choose most specific/authoritative tool
□ Document tool selection reasoning
□ Use web_search only as fallback
□ Verify llms.txt available for FastMCP queries
```

**Common Anti-Patterns:**

| Anti-Pattern | Impact | Fix |
|--------------|--------|-----|
| web_search for FastMCP | Outdated docs | Use llms.txt + web_fetch |
| web_search for repo structure | Incomplete info | Use DeepWiki |
| Not checking tool availability | Suboptimal solution | Analyze before choosing |
| Using generic when specific exists | Lower quality | Prefer specific tools |

---

## Implementation Checklist

Before delivering any FastMCP implementation, verify:

```
✓ All commands use uv (not pip)
✓ FastMCP docs fetched from llms.txt URLs (not web_search)
✓ Tool annotations include readOnlyHint, title, openWorldHint  
✓ Parameters use Annotated[type, Field(description="...")]
✓ Docstrings are single sentence, high-density
✓ Token usage ~65-70% less than verbose approach
✓ Server instructions concise (<100 chars)
✓ Used most appropriate tools (DeepWiki, llms.txt, etc.)
✓ No pip references anywhere
✓ No web_search for FastMCP documentation
✓ Validation constraints in Field (ge, le, pattern)
✓ Error handling specific (ApiError vs generic Exception)
✓ Security measures (input validation, escaping)
```

---

## Impact Summary

### Without These Patterns (V1 - Typical Implementation)
- ❌ Uses pip → ecosystem inconsistency, slower, version conflicts
- ❌ web_search for FastMCP → outdated/incomplete info, 30-50% accuracy
- ❌ Verbose tools → 1200 tokens wasted, poor context efficiency
- ❌ Misses specialized tools → suboptimal solutions, manual work
- ❌ Requires follow-up corrections → 2-3 iteration cycles

**V1 Metrics:**
- Tool descriptions: 1200 tokens
- Implementation time: 3-4 iterations
- Documentation accuracy: 60-70%
- Context efficiency: Poor
- User friction: High (missing docs, wrong patterns)

### With These Patterns (V2 - Optimized Implementation)
- ✅ Uses uv → ecosystem consistency, faster, predictable
- ✅ llms.txt + web_fetch → authoritative docs, 100% accuracy
- ✅ Optimized tools → 380 tokens (820 saved, 68% reduction)
- ✅ Strategic tool use → optimal solutions, automated analysis
- ✅ Production-ready immediately → 0 iterations needed

**V2 Metrics:**
- Tool descriptions: 380 tokens (68% reduction)
- Implementation time: Single iteration
- Documentation accuracy: 100%
- Context efficiency: Excellent
- User friction: None (correct patterns first time)

**Cumulative Benefits:**
- 820 tokens saved per server (68% efficiency gain)
- 3x faster implementation (1 vs 3 iterations)
- 100% vs 65% documentation accuracy
- Zero rework vs 2-3 correction cycles
- Production-ready vs needs refinement

---

## Quick Decision Tree

```
Starting new FastMCP implementation?
│
├─ Will use uv? (not pip)
│  ├─ Yes → Continue
│  └─ No → STOP, fix this first
│
├─ Need FastMCP docs?
│  ├─ Yes → Use llms.txt + web_fetch (not web_search)
│  └─ No → Continue
│
├─ Creating MCP tools?
│  ├─ Yes → Apply optimization patterns
│  │         (annotations, Annotated, concise docstrings)
│  └─ No → Continue
│
└─ Have you checked available tools?
   ├─ Yes → Proceed with best tool for job
   └─ No → STOP, check tool availability first
```

---

## Memory Aid: "UOFT"

**U**v for all dependencies  
**O**ptimize tool descriptions  
**F**etch docs from llms.txt  
**T**ool selection strategic

If you remember UOFT, you remember all four mandatory patterns.

---

## Appendix: Common Scenarios

### Scenario 1: New FastMCP Server from Scratch

```python
# Step 1: Check tools
Available: llms.txt, DeepWiki, web_search

# Step 2: Fetch FastMCP docs
Search: "llms.txt tools authentication"
Fetch: https://gofastmcp.com/servers/tools.md
Fetch: https://gofastmcp.com/servers/auth/authentication.md

# Step 3: Implement with patterns
- uv for all dependencies
- Optimized tool descriptions
- Annotations on all tools
- Annotated parameters
- Single-sentence docstrings

# Step 4: Verify
✓ All UOFT patterns applied
✓ ~68% token reduction achieved
✓ Production-ready immediately
```

### Scenario 2: Optimizing Existing Server

```python
# Step 1: Analyze current state
Current tokens: ~1200 (verbose)
Target tokens: ~380 (optimized)
Reduction goal: 68%

# Step 2: Apply optimizations
For each tool:
1. Add annotations (readOnlyHint, title, openWorldHint)
2. Convert to Annotated parameters with Field
3. Reduce docstring to single sentence
4. Move examples to Field descriptions
5. Add validation constraints (ge, le, pattern)

# Step 3: Update dependencies
Replace all pip → uv
Update README, scripts, docs

# Step 4: Verify
Measure token reduction
Ensure functionality preserved
Check all patterns applied
```

### Scenario 3: Building Progressive Disclosure Server

```python
# Step 1: Research patterns
Fetch: https://gofastmcp.com/servers/tools.md
Review: Gateway pattern examples

# Step 2: Implement gateway
Single tool with action routing:
- discover() → lightweight metadata
- load() → full content on demand
- execute() → run without loading

# Step 3: Optimize
Apply all UOFT patterns
Achieve 85-93% token reduction

# Step 4: Test
Verify progressive loading works
Measure context efficiency
Document usage patterns
```

---

## Further Reading

- FastMCP Documentation: https://gofastmcp.com
- MCP Protocol: https://modelcontextprotocol.io
- Progressive Disclosure: ./PROGRESSIVE_DISCLOSURE.md
- Gateway Patterns: ./GATEWAY_PATTERNS.md
- Tool Optimization: ./OPTIMIZATION_GUIDE.md
