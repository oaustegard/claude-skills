# Progressive Disclosure Architecture

Context management pattern that loads information incrementally. Reduces baseline token consumption by 85-93% while maintaining full functionality.

## Three-Tier Loading

```
Tier 1: Metadata (Always in context)
    ├─ Name
    ├─ Description (~100 words)
    └─ Trigger keywords
    Cost: ~20 tokens per capability

Tier 2: Content (Load on-demand)
    ├─ Full instructions
    ├─ Examples
    └─ Workflow steps
    Cost: ~500 tokens when needed

Tier 3: Execution (No context cost)
    ├─ Run scripts directly
    ├─ Execute validation
    └─ Process without loading source
    Cost: 0 tokens
```

---

## Gateway Pattern Implementation

### Single Tool, Multiple Capabilities

Expose 1 gateway tool that routes internally instead of N tools:

```python
from fastmcp import FastMCP, Context
from typing import Annotated, Literal
from pydantic import Field

mcp = FastMCP(
    name="skills-gateway",
    instructions="Progressive disclosure gateway. Discover skills, load on demand."
)

@mcp.tool(
    annotations={
        "title": "Skill Gateway",
        "readOnlyHint": True,
        "openWorldHint": False
    }
)
async def skill(
    action: Annotated[
        Literal["discover", "load", "run"],
        Field(description="Operation: discover skills, load content, or run script")
    ],
    skill_name: Annotated[
        str | None,
        Field(description="Skill name (from discover results)")
    ] = None,
    params: Annotated[
        dict | None,
        Field(description="Parameters for run action")
    ] = None,
    ctx: Context = None
) -> dict:
    """Gateway to Skills. Progressive disclosure: discover→load→use."""
    
    if action == "discover":
        # Tier 1: Return lightweight metadata only
        skills = []
        for path in find_skill_directories():
            metadata = parse_frontmatter(path / "SKILL.md")
            skills.append({
                "name": metadata["name"],
                "description": metadata["description"],
                "path": str(path)
            })
        return {"skills": skills, "count": len(skills)}
    
    elif action == "load":
        # Tier 2: Load full content on demand
        if not skill_name:
            raise ValueError("skill_name required for load action")
        
        path = find_skill_path(skill_name)
        content = (path / "SKILL.md").read_text()
        return {"skill": skill_name, "content": content}
    
    elif action == "run":
        # Tier 3: Execute without loading source
        if not skill_name:
            raise ValueError("skill_name required for run action")
        
        path = find_skill_path(skill_name)
        script_path = path / "scripts" / f"{params['script']}.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path), *params.get('args', [])],
            capture_output=True,
            text=True
        )
        
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
```

---

## Architecture Comparison

### Traditional MCP (All Upfront)

```
Baseline Context:
├─ Tool 1 schema: 180 tokens
├─ Tool 2 schema: 180 tokens
├─ Tool 3 schema: 180 tokens
├─ Tool 4 schema: 180 tokens
├─ Tool 5 schema: 180 tokens
└─ Tool 6 schema: 180 tokens
Total: 1,080 tokens ALWAYS in context
```

### Gateway MCP (Progressive Disclosure)

```
Baseline Context:
└─ Gateway tool schema: 55 tokens

Tier 1 (discover):
├─ Skill 1 metadata: 20 tokens
├─ Skill 2 metadata: 20 tokens
├─ Skill 3 metadata: 20 tokens
└─ ...
Subtotal: 55 + (N × 20) tokens

Tier 2 (load):
└─ Full skill content: ~500 tokens (ONLY when used)

Tier 3 (run):
└─ Execution result: ~0 tokens
```

**Token Comparison:**

| Scenario | Traditional | Gateway | Savings |
|----------|-------------|---------|---------|
| Baseline (no use) | 1,080 | 55 | 95% |
| Discover capabilities | 1,080 | 230 | 79% |
| Use 1 skill | 1,080 | 730 | 32% |
| Use 3 skills | 1,080 | 1,730 | -60%* |

*Gateway uses more tokens when heavily using multiple capabilities—this is the correct tradeoff.

---

## Implementation Patterns

### Pattern 1: Simple Gateway (Read-Only)

```python
@mcp.tool(annotations={"title": "Data Gateway", "readOnlyHint": True})
async def query(
    action: Literal["list", "get", "search"],
    target: str | None = None,
    params: dict | None = None
) -> dict:
    """Query data. Progressive: list→get→search."""
    
    if action == "list":
        return {"items": get_item_list(), "count": N}
    elif action == "get":
        return {"item": get_item_details(target)}
    elif action == "search":
        return {"results": search_items(params["query"])}
```

### Pattern 2: Full Gateway (With References)

```python
@mcp.tool(annotations={"title": "Skills Gateway", "readOnlyHint": True})
async def skill(
    action: Literal["discover", "load", "list_refs", "read_ref", "run"],
    skill_name: str | None = None,
    ref_path: str | None = None,
    params: dict | None = None
) -> dict:
    """Gateway to Skills. Full progressive disclosure pattern."""
    
    if action == "discover":
        return {"skills": [...], "count": N}
    
    elif action == "load":
        return {"content": load_skill_md(skill_name)}
    
    elif action == "list_refs":
        return {"references": list_reference_files(skill_name)}
    
    elif action == "read_ref":
        return {"content": read_reference_file(skill_name, ref_path)}
    
    elif action == "run":
        return execute_script(skill_name, params)
```

---

## When to Use

**✅ Use gateway when:**
- 5+ related capabilities
- Many capabilities rarely used
- Context efficiency critical
- Capabilities can be logically grouped

**❌ Don't use gateway when:**
- Only 1-3 simple tools
- All capabilities frequently used
- Capabilities completely unrelated
- Complexity outweighs benefits

---

## Context Efficiency Metrics

**Target:**
- Baseline: <100 tokens (single gateway tool)
- Discover: <1000 tokens (up to 50 capabilities)
- Per-use: ~500 tokens (only when capability actually used)
- Overall: 85-93% reduction vs traditional approach

**Formula:**
```python
traditional_tokens = num_tools × avg_tokens_per_tool
gateway_tokens = single_tool_tokens + (metadata × num_capabilities)
savings = 1 - (gateway_tokens / traditional_tokens)
```

---

## Implementation Checklist

```
□ Identify if gateway pattern appropriate (>5 capabilities)
□ Design tier structure (metadata, content, execution)
□ Create discovery mechanism (list capabilities)
□ Implement on-demand loading (fetch when needed)
□ Add execution tier if applicable (scripts/validation)
□ Measure token reduction (target 85-93%)
□ Test progressive loading flow
□ Verify functionality preserved
```
