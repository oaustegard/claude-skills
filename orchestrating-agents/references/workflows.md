# Multi-Agent Coordination Workflows

Detailed examples and patterns for using the multi-agent-coordination skill.

## Example Workflows

### Workflow 1: Multi-Expert Code Review

```python
from claude_client import invoke_parallel

code = """
# Your code here
"""

experts = [
    {"prompt": f"Review for security issues:\n{code}", "system": "Security expert"},
    {"prompt": f"Review for bugs and correctness:\n{code}", "system": "QA expert"},
    {"prompt": f"Review for performance:\n{code}", "system": "Performance expert"},
    {"prompt": f"Review for readability:\n{code}", "system": "Code quality expert"}
]

reviews = invoke_parallel(experts)

print("=== Consolidated Code Review ===")
for expert, review in zip(["Security", "QA", "Performance", "Quality"], reviews):
    print(f"\n## {expert} Perspective\n{review}")
```

### Workflow 2: Parallel Document Analysis

```python
from claude_client import invoke_claude
import glob

documents = glob.glob("docs/*.txt")

# Read all documents
contents = [(doc, open(doc).read()) for doc in documents]

# Analyze in parallel
analyses = invoke_parallel([
    {"prompt": f"Summarize key points from:\n{content}"}
    for doc, content in contents
])

# Synthesize results
synthesis_prompt = "Synthesize these document summaries:\n\n" + "\n\n".join(
    f"Document {i+1}:\n{summary}" for i, summary in enumerate(analyses)
)

final_report = invoke_claude(synthesis_prompt)
print(final_report)
```

### Workflow 3: Recursive Task Delegation

```python
from claude_client import invoke_claude

# Orchestrator delegates subtasks
main_prompt = """
I need to implement a REST API with authentication.
Plan the subtasks and generate prompts for delegation.
"""

plan = invoke_claude(main_prompt, system="You are a project planner")

# Based on plan, delegate specific tasks
subtask_prompts = [
    "Design database schema for user authentication...",
    "Implement JWT token generation and validation...",
    "Create middleware for protected routes..."
]

subtask_results = invoke_parallel([{"prompt": p} for p in subtask_prompts])

# Integrate results
integration_prompt = f"Integrate these implementations:\n\n{subtask_results}"
final_code = invoke_claude(integration_prompt)
```

## Advanced: Agent SDK Delegation Pattern

### When to Use Agent SDK Instances

The functions above use direct Anthropic API calls (stateless, no tools). For sub-agents that need:
- **Tool access**: File system operations, bash commands, code execution
- **Persistent state**: Multi-turn conversations with tool results
- **Sandboxed environments**: Isolated execution contexts

Consider delegating to Claude Agent SDK instances via WebSocket.

### Architecture Overview

```
Main Orchestrator (this skill)
    ↓
Coordination Logic
    ↓
Parallel API Calls          Agent SDK Delegation
(invoke_parallel)           (WebSocket)
    ↓                           ↓
Stateless Analysis         Tool-Enabled Agents
No file access             File system access
                          Bash execution
                          Sandboxed environment
```

### Example: Hybrid Orchestration

```python
from claude_client import invoke_parallel
# Hypothetical agent SDK client (see references below)
from agent_sdk_client import ClaudeAgentClient

# Step 1: Parallel analysis (stateless, fast)
analyses = invoke_parallel([
    {"prompt": "Identify security issues in this design: ..."},
    {"prompt": "Identify performance bottlenecks: ..."},
    {"prompt": "Identify maintainability concerns: ..."}
])

# Step 2: Delegate implementation to tool-enabled agent
agent_client = ClaudeAgentClient(connection_url="...")
agent_client.start()

for analysis in analyses:
    agent_client.send({
        "type": "user_message",
        "data": {
            "message": {
                "role": "user",
                "content": f"Implement fixes for: {analysis}"
            }
        }
    })

    # Agent has access to filesystem, can edit files, run tests

agent_client.stop()
```

### Reference Implementation

For a production WebSocket-based Agent SDK server:
- **Repository**: https://github.com/dzhng/claude-agent
- **Pattern**: E2B-deployed WebSocket server wrapping Agent SDK
- **Use case**: When sub-agents need tool access beyond API completions

### Decision Matrix

| Need | Use invoke_parallel() | Use Agent SDK |
|------|---------------------|---------------|
| Pure analysis/synthesis | ✓ | |
| Multiple perspectives | ✓ | |
| File system operations | | ✓ |
| Bash commands | | ✓ |
| Code execution | | ✓ |
| Sandboxed environment | | ✓ |
| Multi-turn with tools | | ✓ |
| Cost optimization | ✓ (with caching) | |
| Setup complexity | Low | High |

**Rule of thumb**: Use this skill's API functions by default. Only delegate to Agent SDK when tools are essential.

## Prompt Caching Workflows

### Pattern 1: Orchestrator with Parallel Sub-Agents

```python
from claude_client import invoke_parallel

# Orchestrator provides large shared context
codebase = """
<codebase>
...entire codebase (10,000+ tokens)...
</codebase>
"""

# Each sub-agent gets different task with shared cached context
tasks = [
    {"prompt": "Analyze authentication security", "system": "Security expert"},
    {"prompt": "Optimize database queries", "system": "Performance expert"},
    {"prompt": "Improve error handling", "system": "Reliability expert"}
]

# Shared context is cached, 90% cost reduction for subsequent agents
results = invoke_parallel(
    tasks,
    shared_system=codebase,
    cache_shared_system=True
)
```

### Pattern 2: Multi-Round Sub-Agent Conversations

```python
from claude_client import ConversationThread

# Base context for all sub-agents
base_context = [
    {"type": "text", "text": "You are analyzing this codebase:"},
    {"type": "text", "text": "<codebase>...</codebase>", "cache_control": {"type": "ephemeral"}}
]

# Create specialized sub-agent
security_agent = ConversationThread(system=base_context)

# Multiple rounds (each reuses cached context + history)
issue1 = security_agent.send("Find SQL injection vulnerabilities")
issue2 = security_agent.send("Now check for XSS issues")
remediation = security_agent.send("Generate fixes for the issues found")
```

### Pattern 3: Orchestrator + Sub-Agent Multi-Turn

```python
from claude_client import ConversationThread, invoke_parallel

# Step 1: Orchestrator delegates with shared context
shared_context = "<large_documentation>...</large_documentation>"

initial_analyses = invoke_parallel(
    [
        {"prompt": "Identify top 3 bugs"},
        {"prompt": "Identify top 3 performance issues"}
    ],
    shared_system=shared_context,
    cache_shared_system=True
)

# Step 2: Create sub-agents for detailed investigation
bug_agent = ConversationThread(system=shared_context, cache_system=True)
perf_agent = ConversationThread(system=shared_context, cache_system=True)

# Step 3: Multi-turn investigation (reusing cached context)
bug_details = bug_agent.send(f"Analyze this bug: {initial_analyses[0]}")
bug_fix = bug_agent.send("Provide a detailed fix")

perf_details = perf_agent.send(f"Analyze this issue: {initial_analyses[1]}")
perf_solution = perf_agent.send("Provide optimization strategy")
```

### Caching Best Practices

1. **Cache breakpoint placement**:
   - Put stable, large context first (cached)
   - Put variable content after (not cached)
   - Minimum 1,024 tokens per cache breakpoint

2. **Shared context in parallel operations**:
   - ALWAYS use `shared_system` + `cache_shared_system=True` for parallel with common context
   - First agent creates cache, others reuse (5-minute lifetime)
   - All agents must have IDENTICAL shared_system for cache hits

3. **Multi-turn conversations**:
   - Use `ConversationThread` for automatic history caching
   - Each turn caches full history (system + all messages)
   - Subsequent turns reuse cache (significant savings)

4. **Cost optimization**:
   - Cached content: 10% of normal cost (90% savings)
   - Cache for 1000 tokens ≈ $0.0003 vs $0.003 (10x cheaper)
   - For 10 parallel agents with 10K shared context: ~$0.27 vs $3.00
