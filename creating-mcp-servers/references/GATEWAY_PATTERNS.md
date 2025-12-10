# Gateway Patterns for Progressive Disclosure

Complete implementation patterns for building context-efficient MCP servers using the gateway architecture.

## Pattern 1: Read-Only Skills Gateway

**Use Case:** Replicate Claude Skills architecture in MCP

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

SKILLS_DIRS = [
    Path.home() / ".claude" / "skills",
    Path.cwd() / ".claude" / "skills",
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
    skill_name: Annotated[str | None, Field(description="Skill name (from discover)")] = None,
    ref_path: Annotated[str | None, Field(description="Reference path (for read_ref)")] = None,
    script_name: Annotated[str | None, Field(description="Script name (for run)")] = None,
    script_args: Annotated[list[str] | None, Field(description="Script arguments")] = None,
    ctx: Context = None
) -> dict:
    """Gateway to Skills. Progressive disclosure: discover→load→use."""
    
    if action == "discover":
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
        if not skill_name:
            raise ValueError("skill_name required for load action")
        path = find_skill_path(skill_name)
        if not path:
            raise ValueError(f"Skill not found: {skill_name}")
        content = (path / "SKILL.md").read_text()
        refs_dir = path / "references"
        references = []
        if refs_dir.exists():
            references = [str(p.relative_to(path)) for p in refs_dir.rglob("*.md")]
        return {"skill": skill_name, "content": content, "references": references}
    
    elif action == "list_refs":
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
                references.append({
                    "path": rel_path,
                    "name": ref_file.stem,
                    "size": ref_file.stat().st_size
                })
        return {"skill": skill_name, "references": references, "count": len(references)}
    
    elif action == "read_ref":
        if not skill_name or not ref_path:
            raise ValueError("skill_name and ref_path required for read_ref action")
        path = find_skill_path(skill_name)
        if not path:
            raise ValueError(f"Skill not found: {skill_name}")
        ref_file = path / ref_path
        if not ref_file.exists():
            raise ValueError(f"Reference not found: {ref_path}")
        content = ref_file.read_text()
        return {"skill": skill_name, "reference": ref_path, "content": content}
    
    elif action == "run":
        if not skill_name or not script_name:
            raise ValueError("skill_name and script_name required for run action")
        path = find_skill_path(skill_name)
        if not path:
            raise ValueError(f"Skill not found: {skill_name}")
        script_path = path / "scripts" / f"{script_name}.py"
        if not script_path.exists():
            raise ValueError(f"Script not found: {script_name}.py")
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
Baseline: 55 tokens
Discover: 55 + (N × 20) tokens
Traditional: N tools × 80 tokens
Savings: 93% reduction for 10 tools
```

---

## Pattern 2: API Gateway (CRUD Operations)

**Use Case:** Single tool for complete API integration

```python
from fastmcp import FastMCP, Context
from typing import Annotated, Literal
from pydantic import Field
import aiohttp

mcp = FastMCP(
    name="api-gateway",
    instructions="API integration gateway. CRUD operations across resource types."
)

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
        Field(description="CRUD operation")
    ],
    resource_type: Annotated[RESOURCE_TYPES, Field(description="Resource type")],
    identifier: Annotated[str | None, Field(description="Resource ID (for get/update/delete)")] = None,
    query: Annotated[str | None, Field(description="Search query (for search)")] = None,
    data: Annotated[dict | None, Field(description="Data payload (for create/update)")] = None,
    limit: Annotated[int, Field(description="Max results", ge=1, le=100)] = 50,
    ctx: Context = None
) -> dict:
    """API gateway. Progressive: list→get→search→create/update/delete."""
    
    base_url = f"https://api.example.com/{resource_type}"
    
    if action == "list":
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}?limit={limit}") as resp:
                items = await resp.json()
        return {"items": items, "count": len(items)}
    
    elif action == "get":
        if not identifier:
            raise ValueError("identifier required for get action")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/{identifier}") as resp:
                item = await resp.json()
        return {"item": item}
    
    elif action == "search":
        if not query:
            raise ValueError("query required for search action")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/search", params={"q": query, "limit": limit}) as resp:
                results = await resp.json()
        return {"results": results, "count": len(results)}
    
    elif action == "create":
        if not data:
            raise ValueError("data required for create action")
        async with aiohttp.ClientSession() as session:
            async with session.post(base_url, json=data) as resp:
                created = await resp.json()
        return {"created": created}
    
    elif action == "update":
        if not identifier or not data:
            raise ValueError("identifier and data required for update action")
        async with aiohttp.ClientSession() as session:
            async with session.put(f"{base_url}/{identifier}", json=data) as resp:
                updated = await resp.json()
        return {"updated": updated}
    
    elif action == "delete":
        if not identifier:
            raise ValueError("identifier required for delete action")
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{base_url}/{identifier}") as resp:
                success = resp.status == 204
        return {"deleted": success, "identifier": identifier}
```

**Token Efficiency:**
```
Single tool: 55 tokens
6 actions × 4 resource types = 24 virtual endpoints
Traditional: 24 tools × 80 tokens = 1,920 tokens
Savings: 97% reduction
```

---

## Pattern 3: Query Gateway (Database Operations)

**Use Case:** Safe SQL query interface with progressive disclosure

```python
from fastmcp import FastMCP, Context
from typing import Annotated, Literal
from pydantic import Field
import sqlite3

mcp = FastMCP(
    name="query-gateway",
    instructions="Database query interface. Read-only. SQL with parameter escaping."
)

@mcp.tool(
    annotations={
        "title": "Query Gateway",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
async def query(
    action: Annotated[
        Literal["tables", "schema", "validate", "execute"],
        Field(description="Operation: tables, schema, validate, or execute")
    ],
    table: Annotated[str | None, Field(description="Table name (for schema)")] = None,
    sql: Annotated[str | None, Field(description="SQL query (for validate/execute)")] = None,
    limit: Annotated[int, Field(description="Max rows", ge=1, le=1000)] = 100,
    format: Annotated[
        Literal["json", "markdown", "csv"],
        Field(description="Output format")
    ] = "json",
    ctx: Context = None
) -> dict | str:
    """Query database. Progressive: tables→schema→validate→execute."""
    
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        
        if action == "tables":
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            return {"tables": tables, "count": len(tables)}
        
        elif action == "schema":
            if not table:
                raise ValueError("table required for schema action")
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [
                {"name": row["name"], "type": row["type"], "notnull": bool(row["notnull"]), "pk": bool(row["pk"])}
                for row in cursor.fetchall()
            ]
            return {"table": table, "columns": columns, "count": len(columns)}
        
        elif action == "validate":
            if not sql:
                raise ValueError("sql required for validate action")
            try:
                cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
                return {"valid": True, "query": sql}
            except sqlite3.Error as e:
                return {"valid": False, "error": str(e)}
        
        elif action == "execute":
            if not sql:
                raise ValueError("sql required for execute action")
            cursor.execute(f"{sql} LIMIT {limit}")
            rows = cursor.fetchall()
            
            if format == "json":
                results = [dict(row) for row in rows]
                return {"query": sql, "rows": results, "count": len(results)}
            
            elif format == "markdown":
                if not rows:
                    return "No results"
                columns = rows[0].keys()
                lines = []
                lines.append("| " + " | ".join(columns) + " |")
                lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
                for row in rows:
                    values = [str(row[col]) for col in columns]
                    lines.append("| " + " | ".join(values) + " |")
                return "\n".join(lines)
            
            elif format == "csv":
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
Single tool: 55 tokens
4 actions × 3 formats = 12 virtual endpoints
Traditional: 12 tools × 80 tokens = 960 tokens
Savings: 94% reduction
```

---

## Best Practices

### Action-First Design
```python
# ✅ Good: Action determines behavior
@mcp.tool()
async def gateway(action: Literal["list", "get", "create"], ...):
    if action == "list": ...
    elif action == "get": ...

# ❌ Bad: Separate tools for each action
@mcp.tool()
async def list_items(...): ...

@mcp.tool()
async def get_item(...): ...
```

### Optional Parameters by Action
```python
# ✅ Good: Validate by action
async def gateway(
    action: Literal["list", "get"],
    identifier: str | None = None,  # Required only for "get"
):
    if action == "get" and not identifier:
        raise ValueError("identifier required for get")
```

### Context-Aware Error Messages
```python
# ✅ Good: Tell Claude what to do next
raise ValueError(
    "identifier required for get action. "
    "Use list action first to discover available identifiers."
)
```

---

## Anti-Patterns

❌ **Gateway for 1-3 tools** - Complexity outweighs benefit  
❌ **Mix unrelated capabilities** - Create separate gateways instead  
❌ **Overload single action** - Break into specific actions  

---

## Decision Matrix

| Scenario | Pattern | Reason |
|----------|---------|--------|
| 1-3 related operations | Standard tools | Overhead not worth it |
| 5+ related operations | Gateway pattern | Context efficiency wins |
| CRUD on resources | API Gateway | Standardized operations |
| Skills replication | Skills Gateway | Progressive disclosure |
| Database queries | Query Gateway | Safety + flexibility |
| Completely unrelated ops | Separate gateways | Logical separation |

---

## Token Efficiency Targets

```python
traditional_tokens = num_tools * avg_tokens_per_tool
gateway_tokens = single_tool_tokens + (metadata * num_capabilities)
savings = 1 - (gateway_tokens / traditional_tokens)
```

**Targets:**
- Baseline: <100 tokens (single gateway)
- Discovery: <1000 tokens (all capabilities)
- Per-use: Only tokens for capability used
- Overall: 65-93% reduction vs traditional
