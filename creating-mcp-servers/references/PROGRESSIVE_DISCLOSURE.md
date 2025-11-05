# Progressive Disclosure Architecture

## Overview

Progressive disclosure is a context management pattern that loads information incrementally rather than all at once. This architecture, proven in Claude's Skills system, reduces baseline token consumption by 85-93% while maintaining full functionality.

## The Problem

Traditional MCP servers load everything upfront:

```python
# Traditional approach: ALL tools in context immediately
@mcp.tool()
async def tool_1(...): """Detailed description..."""

@mcp.tool()
async def tool_2(...): """Detailed description..."""

@mcp.tool()
async def tool_3(...): """Detailed description..."""

# Result: 82,000 tokens before any conversation begins
```

**Impact:**
- Context window heavily consumed before user asks anything
- Claude has less room for conversation and task execution
- Many tool descriptions never used but always loaded

## The Solution

Skills architecture uses three-tier loading:

```
Tier 1: Metadata (Always in context)
    ├─ Skill name
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

**Results:**
- 85-93% reduction in baseline tokens
- Load content only when Claude needs it
- Execute capabilities without context consumption

---

## Gateway Pattern Implementation

### Single Tool, Multiple Capabilities

Instead of exposing N tools (N schemas in context), expose 1 gateway tool that routes internally:

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
        
        # Execute directly - no source code loaded into context
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

### Usage Flow

**User:** "What skills are available?"

**Claude:**
```python
# Calls: skill(action="discover")
# Returns: {"skills": [{"name": "...", "description": "..."}], "count": N}
# Cost: ~20 tokens per skill metadata
```

**User:** "Help me with commit messages"

**Claude:**
```python
# 1. Recognizes commit-related need
# 2. Calls: skill(action="load", skill_name="Generating Commit Messages")
# 3. Returns: Full SKILL.md content
# Cost: ~500 tokens for detailed instructions

# 4. Follows instructions to help with commit
```

**User:** "Check my code for secrets"

**Claude:**
```python
# 1. Calls: skill(action="load", skill_name="Security Scanner")
# 2. Gets instructions: "Use run action with check_secrets.py script"
# 3. Calls: skill(action="run", skill_name="Security Scanner", 
#           params={"script": "check_secrets", "args": ["file.py"]})
# 4. Returns: {"exit_code": 0, "stdout": "Found 5 issues..."}
# Cost: 0 tokens for script execution
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

Conversation starts with 1,080 tokens already consumed.
```

### Gateway MCP (Progressive Disclosure)

```
Baseline Context:
└─ Gateway tool schema: 55 tokens

Tier 1 (discover):
├─ Skill 1 metadata: 20 tokens
├─ Skill 2 metadata: 20 tokens
├─ Skill 3 metadata: 20 tokens
├─ Skill 4 metadata: 20 tokens
├─ Skill 5 metadata: 20 tokens
└─ Skill 6 metadata: 20 tokens
Subtotal: 175 tokens (loaded when Claude checks capabilities)

Tier 2 (load):
└─ Full skill content: ~500 tokens (loaded ONLY when used)

Tier 3 (run):
└─ Execution result: ~0 tokens (script source never loaded)

Conversation starts with 55 tokens consumed.
Load 175 tokens if Claude checks capabilities.
Load 500 tokens only for skills actually used.
```

**Token Comparison:**

| Scenario | Traditional | Gateway | Savings |
|----------|-------------|---------|---------|
| Baseline (no use) | 1,080 | 55 | 95% |
| Discover capabilities | 1,080 | 230 | 79% |
| Use 1 skill | 1,080 | 730 | 32% |
| Use 3 skills | 1,080 | 1,730 | -60%* |

*Gateway uses more tokens when heavily using multiple capabilities, but this is the correct tradeoff - load only what's actually needed.

---

## Implementation Patterns

### Pattern 1: Simple Gateway (Read-Only Operations)

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

### Pattern 2: Advanced Gateway (Read/Write)

```python
@mcp.tool(annotations={"title": "Resource Gateway", "readOnlyHint": False})
async def resource(
    action: Literal["list", "get", "create", "update", "delete"],
    resource_type: Literal["users", "projects", "tasks"],
    identifier: str | None = None,
    data: dict | None = None
) -> dict:
    """Manage resources. Progressive: list→get→create/update/delete."""
    
    # Route based on action and resource_type
    if action == "list":
        return list_resources(resource_type)
    elif action == "get":
        return get_resource(resource_type, identifier)
    elif action in ["create", "update"]:
        return modify_resource(resource_type, action, identifier, data)
    elif action == "delete":
        return delete_resource(resource_type, identifier)
```

### Pattern 3: Skills Gateway (Full Progressive Disclosure)

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
        # Tier 1: Metadata only
        return {"skills": [...], "count": N}
    
    elif action == "load":
        # Tier 2: Main content
        return {"content": load_skill_md(skill_name)}
    
    elif action == "list_refs":
        # Tier 2.5: Reference file index (no contents)
        return {"references": list_reference_files(skill_name)}
    
    elif action == "read_ref":
        # Tier 2.5: Specific reference content
        return {"content": read_reference_file(skill_name, ref_path)}
    
    elif action == "run":
        # Tier 3: Execute without loading source
        return execute_script(skill_name, params)
```

---

## Context Efficiency Metrics

### Real-World Example: Desktop Commander MCP

**Before (Traditional MCP):**
```
29 tools × ~80 tokens/tool = 2,320 tokens baseline
+ Detailed descriptions = ~82,000 tokens total
Efficiency: Poor (massive context consumption)
```

**After (Gateway Pattern):**
```
1 tool × 55 tokens = 55 tokens baseline
+ Metadata on discover: 29 capabilities × 20 tokens = 580 tokens
+ Load on demand: ~500 tokens per capability used
Efficiency: 95% reduction in baseline, 97.5% overall
```

### Efficiency Formula

```python
# Traditional MCP
baseline_tokens = num_tools × avg_tokens_per_tool
efficiency = "Poor" if baseline_tokens > 500 else "Acceptable"

# Gateway MCP
baseline_tokens = single_gateway_tool  # ~55 tokens
discover_cost = num_capabilities × 20  # Metadata only
load_cost = capabilities_used × 500    # On-demand content
total_tokens = baseline_tokens + discover_cost + load_cost
efficiency_gain = 1 - (total_tokens / traditional_baseline)
```

**Target Metrics:**
- Baseline: <100 tokens (single gateway tool)
- Discover: <1000 tokens (up to 50 capabilities)
- Per-use: ~500 tokens (only when capability actually used)
- Overall: 85-93% reduction vs traditional approach

---

## Benefits Analysis

### Immediate Benefits

**Context Window Preservation:**
- Start conversations with minimal token consumption
- Reserve context for actual work, not capability descriptions
- Scale to hundreds of capabilities without bloat

**Pay-As-You-Go Loading:**
- Load content only when Claude determines it's needed
- No wasted tokens on unused capabilities
- Intelligent resource allocation

**Execution Without Loading:**
- Run validation scripts directly
- Process data without source code in context
- Deterministic operations with zero token cost

### Long-Term Benefits

**Scalability:**
- Add capabilities without increasing baseline cost
- 1 tool in client interface vs N tools
- Clean, manageable server architecture

**Maintainability:**
- Single routing function vs many tool definitions
- Easier to add/remove capabilities
- Consistent interface patterns

**User Experience:**
- Faster initial responses (less context to process)
- Better at complex tasks (more room for reasoning)
- Claude decides when to load capabilities

---

## Implementation Checklist

Before implementing progressive disclosure:

```
□ Identify if gateway pattern appropriate (>5 capabilities)
□ Design tier structure (metadata, content, execution)
□ Create discovery mechanism (list capabilities)
□ Implement on-demand loading (fetch when needed)
□ Add execution tier if applicable (scripts/validation)
□ Measure token reduction (target 85-93%)
□ Document usage patterns for users
□ Test progressive loading flow
□ Verify functionality preserved
□ Compare efficiency vs traditional approach
```

---

## Common Patterns

### Pattern: Validation Without Loading

```python
@mcp.tool()
async def validate(
    check_type: Literal["security", "style", "types"],
    file_path: str
) -> dict:
    """Run validation without loading validator source."""
    
    # Map check types to scripts
    scripts = {
        "security": "check_secrets.py",
        "style": "check_style.py",
        "types": "check_types.py"
    }
    
    script = scripts_dir / scripts[check_type]
    result = subprocess.run(
        [sys.executable, str(script), file_path],
        capture_output=True,
        text=True
    )
    
    return {
        "passed": result.returncode == 0,
        "issues": parse_output(result.stdout)
    }
    # Validator source never loaded into context
```

### Pattern: Nested Progressive Disclosure

```python
# Level 1: Discover domains
skill(action="discover") 
# → {"skills": ["Skill A", "Skill B", "Skill C"]}

# Level 2: Load skill
skill(action="load", skill_name="Skill A")
# → {"content": "...", "references": ["ref1.md", "ref2.md"]}

# Level 3: Load reference
skill(action="read_ref", skill_name="Skill A", ref_path="ref1.md")
# → {"content": "Detailed reference material..."}

# Level 4: Execute
skill(action="run", skill_name="Skill A", params={...})
# → {"result": "...", "exit_code": 0}
```

### Pattern: Lazy Loading with Caching

```python
# In-memory cache for loaded content
_content_cache: dict[str, str] = {}

@mcp.tool()
async def skill(action: str, skill_name: str | None = None) -> dict:
    """Gateway with caching for repeated access."""
    
    if action == "load":
        # Check cache first
        if skill_name in _content_cache:
            return {"content": _content_cache[skill_name], "cached": True}
        
        # Load and cache
        content = load_skill_md(skill_name)
        _content_cache[skill_name] = content
        return {"content": content, "cached": False}
```

---

## Performance Considerations

### When to Use Gateway Pattern

**✅ Use gateway when:**
- You have >5 related capabilities
- Many capabilities rarely used
- Context efficiency critical
- Capabilities can be logically grouped
- You need scalability

**❌ Don't use gateway when:**
- Only 1-3 simple tools
- All capabilities frequently used
- Capabilities completely unrelated
- Complexity outweighs benefits

### Optimization Tips

1. **Keep metadata tiny** (~20 tokens per capability)
2. **Load content lazily** (only when Claude needs it)
3. **Execute without loading** (scripts run directly)
4. **Cache intelligently** (avoid reloading same content)
5. **Measure religiously** (track token consumption)

---

## Conclusion

Progressive disclosure through gateway patterns achieves:
- **85-93% baseline token reduction**
- **Scalable architecture** (1 tool vs N tools)
- **Pay-as-you-go loading** (only what's needed)
- **Execution without context cost** (run scripts directly)

This is the architecture that powers Claude Skills and can be replicated in any MCP server for maximum context efficiency.

## Further Reading

- FastMCP Tools Documentation: https://gofastmcp.com/servers/tools.md
- Gateway Pattern Examples: ./GATEWAY_PATTERNS.md
- Skills Architecture: (Claude Skills documentation)
- Token Optimization: ./OPTIMIZATION_GUIDE.md
