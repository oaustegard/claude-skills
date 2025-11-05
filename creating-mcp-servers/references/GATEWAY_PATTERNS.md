# Gateway Patterns for Progressive Disclosure

Complete implementation patterns for building context-efficient MCP servers using the gateway architecture.

## Pattern Overview

Gateway patterns use a single MCP tool that internally routes to multiple capabilities, combining MCP's client-side execution with Skills' progressive disclosure for maximum context efficiency.

**Key Benefits:**
- Single tool schema (vs N tool schemas)
- Load content only when needed
- Execute without context consumption
- Scales to hundreds of capabilities

---

## Pattern 1: Read-Only Skills Gateway

**Use Case:** Replicate Claude Skills architecture in MCP

**Architecture:**
```
Single tool: skill(action, skill_name, params)
├─ discover → List all skills (metadata only)
├─ load → Fetch skill content on demand
├─ list_refs → List reference files (no content)
├─ read_ref → Fetch specific reference
└─ run → Execute script without loading source
```

**Complete Implementation:**

```python
from fastmcp import FastMCP, Context
from pathlib import Path
from typing import Annotated, Literal
from pydantic import Field
import yaml
import subprocess
import sys

mcp = FastMCP(
    name="skills-gateway",
    instructions="Claude Skills for MCP. Discover skills, load on demand."
)

# Configuration
SKILLS_DIRS = [
    Path.home() / ".claude" / "skills",  # User skills
    Path.cwd() / ".claude" / "skills",   # Project skills
]

def find_skill_directories() -> list[Path]:
    """Find all skill directories."""
    skills = []
    for base_dir in SKILLS_DIRS:
        if base_dir.exists():
            for path in base_dir.iterdir():
                if path.is_dir() and (path / "SKILL.md").exists():
                    skills.append(path)
    return skills

def parse_skill_frontmatter(skill_path: Path) -> dict:
    """Extract YAML frontmatter from SKILL.md."""
    content = (skill_path / "SKILL.md").read_text()
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            frontmatter = content[4:end]
            return yaml.safe_load(frontmatter)
    return {}

def find_skill_path(skill_name: str) -> Path | None:
    """Find path for named skill."""
    for path in find_skill_directories():
        metadata = parse_skill_frontmatter(path)
        if metadata.get("name") == skill_name:
            return path
    return None

@mcp.tool(
    annotations={
        "title": "Skill Gateway",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
async def skill(
    action: Annotated[
        Literal["discover", "load", "list_refs", "read_ref", "run"],
        Field(description="Operation: discover, load, list_refs, read_ref, or run")
    ],
    skill_name: Annotated[
        str | None,
        Field(description="Skill name (from discover results)")
    ] = None,
    ref_path: Annotated[
        str | None,
        Field(description="Reference file path (for read_ref)")
    ] = None,
    script_name: Annotated[
        str | None,
        Field(description="Script name (for run)")
    ] = None,
    script_args: Annotated[
        list[str] | None,
        Field(description="Script arguments (for run)")
    ] = None,
    ctx: Context = None
) -> dict:
    """Gateway to Skills. Progressive disclosure: discover→load→use."""
    
    if action == "discover":
        # Tier 1: Return lightweight metadata only (~20 tokens/skill)
        skills = []
        for path in find_skill_directories():
            metadata = parse_skill_frontmatter(path)
            skills.append({
                "name": metadata.get("name", "unknown"),
                "description": metadata.get("description", ""),
                "path": str(path)
            })
        
        return {"skills": skills, "count": len(skills)}
    
    elif action == "load":
        # Tier 2: Load full content on demand (~500 tokens)
        if not skill_name:
            raise ValueError("skill_name required for load action")
        
        path = find_skill_path(skill_name)
        if not path:
            raise ValueError(f"Skill not found: {skill_name}")
        
        content = (path / "SKILL.md").read_text()
        
        # Check for reference files
        refs_dir = path / "references"
        references = []
        if refs_dir.exists():
            references = [str(p.relative_to(path)) for p in refs_dir.rglob("*.md")]
        
        return {
            "skill": skill_name,
            "content": content,
            "references": references
        }
    
    elif action == "list_refs":
        # Tier 2.5: List reference files without content
        if not skill_name:
            raise ValueError("skill_name required for list_refs action")
        
        path = find_skill_path(skill_name)
        if not path:
            raise ValueError(f"Skill not found: {skill_name}")
        
        refs_dir = path / "references"
        references = []
        if refs_dir.exists():
            for ref_file in refs_dir.rglob("*.md"):
                rel_path = str(ref_file.relative_to(path))
                # Just list filenames, no content
                references.append({
                    "path": rel_path,
                    "name": ref_file.stem,
                    "size": ref_file.stat().st_size
                })
        
        return {
            "skill": skill_name,
            "references": references,
            "count": len(references)
        }
    
    elif action == "read_ref":
        # Tier 2.5: Read specific reference file
        if not skill_name or not ref_path:
            raise ValueError("skill_name and ref_path required for read_ref action")
        
        path = find_skill_path(skill_name)
        if not path:
            raise ValueError(f"Skill not found: {skill_name}")
        
        ref_file = path / ref_path
        if not ref_file.exists():
            raise ValueError(f"Reference not found: {ref_path}")
        
        content = ref_file.read_text()
        return {
            "skill": skill_name,
            "reference": ref_path,
            "content": content
        }
    
    elif action == "run":
        # Tier 3: Execute script without loading source (~0 tokens)
        if not skill_name or not script_name:
            raise ValueError("skill_name and script_name required for run action")
        
        path = find_skill_path(skill_name)
        if not path:
            raise ValueError(f"Skill not found: {skill_name}")
        
        script_path = path / "scripts" / f"{script_name}.py"
        if not script_path.exists():
            raise ValueError(f"Script not found: {script_name}.py")
        
        # Execute directly - source code never loaded into context
        result = subprocess.run(
            [sys.executable, str(script_path), *(script_args or [])],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            "skill": skill_name,
            "script": script_name,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    
    else:
        raise ValueError(f"Unknown action: {action}")
```

**Token Efficiency:**
```
Baseline: 1 tool × 55 tokens = 55 tokens
Discover: 55 + (N skills × 20) = 55 + 200 tokens (10 skills)
Load: 55 + 500 tokens = 555 tokens (when used)
Run: 55 + 0 tokens = 55 tokens (execution only)

Traditional: N tools × 80 tokens = 800 tokens (10 tools)
Savings: 745 tokens baseline (93% reduction)
```

---

## Pattern 2: API Gateway (Read/Write Operations)

**Use Case:** Single tool for complete API integration

**Architecture:**
```
Single tool: api(action, resource_type, identifier, data)
├─ list → List resources by type
├─ get → Retrieve specific resource
├─ search → Find resources by query
├─ create → Create new resource
├─ update → Modify existing resource
└─ delete → Remove resource
```

**Implementation:**

```python
from fastmcp import FastMCP, Context
from typing import Annotated, Literal
from pydantic import Field
import aiohttp

mcp = FastMCP(
    name="api-gateway",
    instructions="API integration gateway. CRUD operations across resource types."
)

# Resource types
RESOURCE_TYPES = Literal["users", "projects", "tasks", "comments"]

@mcp.tool(
    annotations={
        "title": "API Gateway",
        "readOnlyHint": False,
        "openWorldHint": True
    }
)
async def api(
    action: Annotated[
        Literal["list", "get", "search", "create", "update", "delete"],
        Field(description="Operation: list, get, search, create, update, delete")
    ],
    resource_type: Annotated[
        RESOURCE_TYPES,
        Field(description="Resource type: users, projects, tasks, comments")
    ],
    identifier: Annotated[
        str | None,
        Field(description="Resource ID (for get, update, delete)")
    ] = None,
    query: Annotated[
        str | None,
        Field(description="Search query (for search)")
    ] = None,
    data: Annotated[
        dict | None,
        Field(description="Resource data (for create, update)")
    ] = None,
    limit: Annotated[
        int,
        Field(description="Max results (for list, search)", ge=1, le=100)
    ] = 50,
    ctx: Context = None
) -> dict:
    """API gateway. CRUD operations: list→get→create/update/delete."""
    
    # Base URL from environment
    base_url = os.getenv("API_URL", "https://api.example.com")
    api_key = os.getenv("API_KEY")
    
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        
        if action == "list":
            # List resources
            url = f"{base_url}/{resource_type}"
            params = {"limit": limit}
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return {
                    "resource_type": resource_type,
                    "items": data.get("items", []),
                    "count": len(data.get("items", []))
                }
        
        elif action == "get":
            # Get specific resource
            if not identifier:
                raise ValueError("identifier required for get action")
            
            url = f"{base_url}/{resource_type}/{identifier}"
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return {
                    "resource_type": resource_type,
                    "identifier": identifier,
                    "data": data
                }
        
        elif action == "search":
            # Search resources
            if not query:
                raise ValueError("query required for search action")
            
            url = f"{base_url}/{resource_type}/search"
            params = {"q": query, "limit": limit}
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return {
                    "resource_type": resource_type,
                    "query": query,
                    "results": data.get("results", []),
                    "count": len(data.get("results", []))
                }
        
        elif action == "create":
            # Create resource
            if not data:
                raise ValueError("data required for create action")
            
            url = f"{base_url}/{resource_type}"
            async with session.post(url, json=data) as resp:
                resp.raise_for_status()
                result = await resp.json()
                return {
                    "resource_type": resource_type,
                    "action": "created",
                    "data": result
                }
        
        elif action == "update":
            # Update resource
            if not identifier or not data:
                raise ValueError("identifier and data required for update action")
            
            url = f"{base_url}/{resource_type}/{identifier}"
            async with session.patch(url, json=data) as resp:
                resp.raise_for_status()
                result = await resp.json()
                return {
                    "resource_type": resource_type,
                    "identifier": identifier,
                    "action": "updated",
                    "data": result
                }
        
        elif action == "delete":
            # Delete resource
            if not identifier:
                raise ValueError("identifier required for delete action")
            
            url = f"{base_url}/{resource_type}/{identifier}"
            async with session.delete(url) as resp:
                resp.raise_for_status()
                return {
                    "resource_type": resource_type,
                    "identifier": identifier,
                    "action": "deleted"
                }
```

**Usage Flow:**
```python
# List resources
api(action="list", resource_type="projects", limit=10)

# Get specific
api(action="get", resource_type="projects", identifier="proj-123")

# Search
api(action="search", resource_type="tasks", query="urgent", limit=20)

# Create
api(action="create", resource_type="tasks", data={
    "title": "New task",
    "project_id": "proj-123"
})

# Update
api(action="update", resource_type="tasks", identifier="task-456", data={
    "status": "completed"
})

# Delete
api(action="delete", resource_type="tasks", identifier="task-456")
```

---

## Pattern 3: Query Gateway (Database Operations)

**Use Case:** Safe database queries with multiple output formats

**Architecture:**
```
Single tool: query(action, query, format, params)
├─ tables → List available tables
├─ schema → Get table schema
├─ execute → Run SELECT query
└─ validate → Validate query without execution
```

**Implementation:**

```python
from fastmcp import FastMCP, Context
from typing import Annotated, Literal
from pydantic import Field
import sqlite3
import json

mcp = FastMCP(
    name="query-gateway",
    instructions="Database query gateway. Read-only operations with multiple output formats."
)

DB_PATH = "database.db"

@mcp.tool(
    annotations={
        "title": "Query Gateway",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
async def query(
    action: Annotated[
        Literal["tables", "schema", "execute", "validate"],
        Field(description="Operation: tables, schema, execute, validate")
    ],
    table: Annotated[
        str | None,
        Field(description="Table name (for schema)")
    ] = None,
    sql: Annotated[
        str | None,
        Field(description="SQL query (for execute, validate)")
    ] = None,
    format: Annotated[
        Literal["json", "markdown", "csv"],
        Field(description="Output format (for execute)")
    ] = "json",
    limit: Annotated[
        int,
        Field(description="Max rows (for execute)", ge=1, le=1000)
    ] = 100,
    ctx: Context = None
) -> dict | str:
    """Query gateway. Safe DB operations: tables→schema→execute."""
    
    # Validate read-only queries
    if sql and action in ["execute", "validate"]:
        sql_lower = sql.lower().strip()
        if not sql_lower.startswith("select"):
            raise ValueError("Only SELECT queries allowed (read-only)")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        if action == "tables":
            # List all tables
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]
            return {"tables": tables, "count": len(tables)}
        
        elif action == "schema":
            # Get table schema
            if not table:
                raise ValueError("table required for schema action")
            
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "notnull": bool(row["notnull"]),
                    "pk": bool(row["pk"])
                }
                for row in cursor.fetchall()
            ]
            
            return {
                "table": table,
                "columns": columns,
                "count": len(columns)
            }
        
        elif action == "validate":
            # Validate query without executing
            if not sql:
                raise ValueError("sql required for validate action")
            
            try:
                cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
                return {"valid": True, "query": sql}
            except sqlite3.Error as e:
                return {"valid": False, "error": str(e)}
        
        elif action == "execute":
            # Execute query with format
            if not sql:
                raise ValueError("sql required for execute action")
            
            cursor.execute(f"{sql} LIMIT {limit}")
            rows = cursor.fetchall()
            
            if format == "json":
                # JSON format
                results = [dict(row) for row in rows]
                return {
                    "query": sql,
                    "rows": results,
                    "count": len(results)
                }
            
            elif format == "markdown":
                # Markdown table format
                if not rows:
                    return "No results"
                
                # Get column names
                columns = rows[0].keys()
                
                # Build markdown table
                lines = []
                lines.append("| " + " | ".join(columns) + " |")
                lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
                
                for row in rows:
                    values = [str(row[col]) for col in columns]
                    lines.append("| " + " | ".join(values) + " |")
                
                return "\n".join(lines)
            
            elif format == "csv":
                # CSV format
                if not rows:
                    return ""
                
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
                
                return output.getvalue()
    
    finally:
        conn.close()
```

**Token Efficiency:**
```
Single tool: 55 tokens baseline
4 actions: tables, schema, execute, validate
Multiple formats: json, markdown, csv

Traditional approach: 12 tools (4 actions × 3 formats)
Traditional baseline: 12 × 80 = 960 tokens
Savings: 905 tokens (94% reduction)
```

---

## Best Practices

### 1. Action-First Design

```python
# ✅ Good: Action determines behavior
@mcp.tool()
async def gateway(action: Literal["list", "get", "create"], ...):
    if action == "list": ...
    elif action == "get": ...
    elif action == "create": ...

# ❌ Bad: Separate tools for each action
@mcp.tool()
async def list_items(...): ...

@mcp.tool()
async def get_item(...): ...

@mcp.tool()
async def create_item(...): ...
```

### 2. Optional Parameters by Action

```python
# ✅ Good: Parameters optional, validated by action
async def gateway(
    action: Literal["list", "get"],
    identifier: str | None = None,  # Required only for "get"
    limit: int = 50                  # Required only for "list"
):
    if action == "get" and not identifier:
        raise ValueError("identifier required for get")

# ❌ Bad: All parameters always required
async def gateway(action: str, identifier: str, limit: int):
    ...
```

### 3. Clear Action Descriptions

```python
# ✅ Good: Explain action flow in docstring
"""Gateway to resources. Progressive: list→get→create/update/delete."""

# ❌ Bad: Vague description
"""Manage resources."""
```

### 4. Validate Early

```python
# ✅ Good: Validate action and params upfront
if action == "get":
    if not identifier:
        raise ValueError("identifier required for get action")
    return fetch_resource(identifier)

# ❌ Bad: Fail during execution
async def gateway(action, identifier):
    # Only discovers missing identifier after API call
    return await api.get(identifier)  # Fails if None
```

### 5. Context-Aware Error Messages

```python
# ✅ Good: Tell Claude what to do next
raise ValueError(
    "identifier required for get action. "
    "Use list action first to discover available identifiers."
)

# ❌ Bad: Generic error
raise ValueError("Missing parameter")
```

---

## Anti-Patterns

### ❌ Don't: Create Gateway for 1-3 Tools

```python
# Not worth the complexity
@mcp.tool()
async def gateway(action: Literal["single_action"]):
    return do_thing()

# Just use regular tool instead
@mcp.tool()
async def do_thing():
    return result
```

### ❌ Don't: Mix Unrelated Capabilities

```python
# Bad: Mixing completely unrelated operations
@mcp.tool()
async def gateway(action: Literal["send_email", "query_database", "render_image"]):
    ...

# Good: Separate gateways for unrelated domains
@mcp.tool()
async def email_gateway(...): ...

@mcp.tool()
async def database_gateway(...): ...
```

### ❌ Don't: Overload Single Action

```python
# Bad: Single action doing too much
if action == "query":
    # 200+ lines of complex logic
    ...

# Good: Break into specific actions
if action == "search": ...
elif action == "filter": ...
elif action == "aggregate": ...
```

---

## Decision Matrix

| Scenario | Pattern | Reason |
|----------|---------|--------|
| 1-3 related operations | Standard tools | Overhead not worth it |
| 5+ related operations | Gateway pattern | Context efficiency wins |
| CRUD on resources | API Gateway (Pattern 2) | Standardized operations |
| Skills replication | Skills Gateway (Pattern 1) | Progressive disclosure |
| Database queries | Query Gateway (Pattern 3) | Safety + flexibility |
| Completely unrelated ops | Separate gateways | Logical separation |

---

## Measuring Success

```python
# Calculate token efficiency
traditional_tokens = num_tools * avg_tokens_per_tool
gateway_tokens = single_tool_tokens + (metadata * num_capabilities)
savings = 1 - (gateway_tokens / traditional_tokens)

# Example:
# Traditional: 10 tools × 80 tokens = 800 tokens
# Gateway: 55 + (20 × 10) = 255 tokens
# Savings: 68%
```

**Target Metrics:**
- Baseline: <100 tokens (single gateway)
- Discovery: <1000 tokens (all capabilities)
- Per-use: Only tokens for capability used
- Overall: 65-93% reduction vs traditional

---

## Complete Working Example

See `scripts/gateway_example.py` for a complete, runnable implementation combining all patterns.

---

## Further Reading

- Progressive Disclosure: ./PROGRESSIVE_DISCLOSURE.md
- Tool Optimization: ./OPTIMIZATION_GUIDE.md
- MCPB Bundling: ./MCPB_BUNDLING.md
- FastMCP Tools: https://gofastmcp.com/servers/tools.md
