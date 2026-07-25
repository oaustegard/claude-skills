---
name: orchestrating-agents
description: Orchestrates parallel API instances, delegated sub-tasks, and multi-agent workflows with streaming and tool-enabled delegation patterns. Use for parallel analysis, multi-perspective reviews, or complex task decomposition.
metadata:
  version: 0.4.1
---

## SURFACE ROUTING — read first

This skill hand-rolls subagent orchestration via raw Anthropic API calls. A
managed runtime now does the same job. Which one to use depends on your surface:

- **In Claude Code (incl. CCotw): use the native runtime, NOT this skill.** If you
  can invoke `/deep-research`, trigger a run with the `workflow` keyword, set
  `/effort ultracode`, or spawn Task subagents — do that instead. The runtime gives
  16-concurrent / 1000-agent ceilings, an approval gate, adversarial cross-review,
  and in-session resume that this skill would otherwise reimplement badly. Dynamic
  workflows shipped in research preview (Claude Code v2.1.154+, 2026).
- **In claude.ai chat or the bare API (no workflow runtime): use this skill.**
  Parallel API instances over httpx is the only fan-out path here. Proceed below.

Discriminator: do you have a native subagent/Task tool or a workflow command? Yes
→ native. No → this skill. Never reimplement the runtime where it already exists.

# Orchestrating Agents

This skill enables programmatic API invocations for advanced workflows including parallel processing, task delegation, and multi-agent analysis using the Anthropic API.

## When to Use This Skill

**Primary use cases:**
- **Parallel sub-tasks**: Break complex analysis into simultaneous independent streams
- **Multi-perspective analysis**: Get 3-5 different expert viewpoints concurrently
- **Delegation**: Offload specific subtasks to specialized API instances
- **Recursive workflows**: Orchestrator coordinating multiple API instances
- **High-volume processing**: Batch process multiple items concurrently

**Trigger patterns:**
- "Parallel analysis", "multi-perspective review", "concurrent processing"
- "Delegate subtasks", "coordinate multiple agents"
- "Run analyses from different perspectives"
- "Get expert opinions from multiple angles"

## Quick Start

### Single Invocation

```python
import sys
sys.path.append('/home/user/claude-skills/orchestrating-agents/scripts')
from claude_client import invoke_claude

response = invoke_claude(
    prompt="Analyze this code for security vulnerabilities: ...",
    model="claude-sonnet-4-6"
)
print(response)
```

### Parallel Multi-Perspective Analysis

```python
from claude_client import invoke_parallel

prompts = [
    {
        "prompt": "Analyze from security perspective: ...",
        "system": "You are a security expert"
    },
    {
        "prompt": "Analyze from performance perspective: ...",
        "system": "You are a performance optimization expert"
    },
    {
        "prompt": "Analyze from maintainability perspective: ...",
        "system": "You are a software architecture expert"
    }
]

results = invoke_parallel(prompts, model="claude-sonnet-4-6")

for i, result in enumerate(results):
    print(f"\n=== Perspective {i+1} ===")
    print(result)
```

### Parallel with Shared Cached Context (Recommended)

For parallel operations with shared base context, use caching to reduce costs by up to 90%:

```python
from claude_client import invoke_parallel

# Large context shared across all sub-agents (e.g., codebase, documentation)
base_context = """
<codebase>
...large codebase or documentation (1000+ tokens)...
</codebase>
"""

prompts = [
    {"prompt": "Find security vulnerabilities in the authentication module"},
    {"prompt": "Identify performance bottlenecks in the API layer"},
    {"prompt": "Suggest refactoring opportunities in the database layer"}
]

# First sub-agent creates cache, subsequent ones reuse it
results = invoke_parallel(
    prompts,
    shared_system=base_context,
    cache_shared_system=True  # 90% cost reduction for cached content
)
```

### Multi-Turn Conversation with Auto-Caching

For sub-agents that need multiple rounds of conversation:

```python
from claude_client import ConversationThread

# Create a conversation thread (auto-caches history)
agent = ConversationThread(
    system="You are a code refactoring expert with access to the codebase",
    cache_system=True
)

# Turn 1: Initial analysis
response1 = agent.send("Analyze the UserAuth class for issues")
print(response1)

# Turn 2: Follow-up (reuses cached system + turn 1)
response2 = agent.send("How would you refactor the login method?")
print(response2)

# Turn 3: Implementation (reuses all previous context)
response3 = agent.send("Show me the refactored code")
print(response3)
```

### Streaming Responses

For real-time feedback from sub-agents:

```python
from claude_client import invoke_claude_streaming

def show_progress(chunk):
    print(chunk, end='', flush=True)

response = invoke_claude_streaming(
    "Write a comprehensive security analysis...",
    callback=show_progress
)
```

### Parallel Streaming

Monitor multiple sub-agents simultaneously:

```python
from claude_client import invoke_parallel_streaming

def agent1_callback(chunk):
    print(f"[Security] {chunk}", end='', flush=True)

def agent2_callback(chunk):
    print(f"[Performance] {chunk}", end='', flush=True)

results = invoke_parallel_streaming(
    [
        {"prompt": "Security review: ..."},
        {"prompt": "Performance review: ..."}
    ],
    callbacks=[agent1_callback, agent2_callback]
)
```

### Interruptible Operations

Cancel long-running parallel operations:

```python
from claude_client import invoke_parallel_interruptible, InterruptToken
import threading
import time

token = InterruptToken()

# Run in background
def run_analysis():
    results = invoke_parallel_interruptible(
        prompts=[...],
        interrupt_token=token
    )
    return results

thread = threading.Thread(target=run_analysis)
thread.start()

# Interrupt after 5 seconds
time.sleep(5)
token.interrupt()
```

## Core Functions

| Function | Module | Purpose |
|---|---|---|
| `invoke_claude()` | core | Single synchronous invocation, full parameter control |
| `invoke_parallel()` | core | Concurrent invocations, results in input order |
| `invoke_claude_streaming()` | core | Single invocation, token-by-token callback |
| `invoke_parallel_streaming()` | core | Concurrent invocations with per-agent stream callbacks |
| `invoke_parallel_interruptible()` | core | Concurrent invocations cancellable mid-flight |
| `ConversationThread` | core | Stateful multi-turn thread with cached history |
| `StallDetector` | core | Flags agents idle beyond a timeout |
| `TaskTracker` | task_state | Tracks task status across an orchestration run |
| `invoke_with_retry()` | orchestration | Single invocation with backoff on transient errors |
| `invoke_parallel_managed()` | orchestration | Concurrency-limited parallel run with retry, stall hooks, reconciliation |

Full signatures, parameters, and worked examples for each:
[references/function-reference.md](references/function-reference.md).

## Example Workflows

See [references/workflows.md](references/workflows.md) for detailed examples including:
- Multi-expert code review
- Parallel document analysis
- Recursive task delegation
- Advanced Agent SDK delegation patterns
- Prompt caching workflows

## Execute Mode (Default Sub-Agent Prompt)

For autonomous sub-agents that should execute without asking questions:

```python
from claude_client import invoke_claude, EXECUTE_MODE

response = invoke_claude(
    prompt="Review auth.py for SQL injection vulnerabilities",
    system=f"You are a security expert.\n\n{EXECUTE_MODE}"
)
```

`EXECUTE_MODE` encodes these principles (adapted from OpenAI Codex):
- Make assumptions instead of asking questions; state them briefly
- Think ahead: what else might be needed?
- Report failures with what you tried and what you'll do next
- Summarize deliverables and how to validate them

## Agent Pool (Named Agents with Messaging)

For workflows where multiple agents need to communicate:

```python
from agent_pool import AgentPool

pool = AgentPool(
    shared_system="You are reviewing the auth module of a web app.",
    max_depth=3,    # prevent recursive spawn explosion
    max_agents=10,
)

# Spawn named agents with roles
pool.spawn("security", system=f"Focus on vulnerabilities.\n\n{pool.EXECUTE_MODE}")
pool.spawn("perf", system=f"Focus on performance.\n\n{pool.EXECUTE_MODE}")

# Run turns (pending inter-agent messages auto-injected)
sec_result = pool.run("security", "Review the login flow")

# Agent-to-agent messaging
pool.send("security", to="perf",
          content="Auth does N+1 queries in the session check loop",
          trigger_turn=True)  # auto-runs perf with this context

# Broadcast to all agents
pool.broadcast("security", "Auth uses bcrypt cost=12, 200ms per hash")

# Query pool state
pool.agents()           # ["security", "perf"]
pool.agent_info("perf") # {name, depth, children, pending_messages, turns}
```

### Spawn Reservation (Atomic Agent Creation)

For complex workflows where agent creation might fail:

```python
from agent_pool import AgentPool

pool = AgentPool(shared_system="Code review team")

# Reservation pattern: name is reserved, rolled back on exception
with pool.reserve("analyst", parent="lead") as res:
    res.configure(system="You analyze code complexity.", model="claude-opus-4-6")
    # If configure or any other work raises, the name is released
# Agent "analyst" is now live

# Depth limits prevent unbounded recursion
pool.spawn("sub-analyst", parent="analyst")  # depth=2, OK
pool.spawn("sub-sub", parent="sub-analyst")  # depth=3, raises ValueError
```

### When to Use AgentPool vs invoke_parallel

| Pattern | Use When |
|---------|----------|
| `invoke_parallel()` | Independent tasks, no inter-agent communication needed |
| `AgentPool` | Agents need to share findings, build on each other's work, or have parent/child relationships |
| `invoke_parallel_managed()` | Independent tasks with retry, stall detection, concurrency limits |



## Setup

**Prerequisites:**

1. Install anthropic library:
   ```bash
   uv pip install anthropic
   ```

2. Configure API key via project knowledge file:

   **Option 1 (recommended): Individual file**
   - Create document: `ANTHROPIC_API_KEY.txt`
   - Content: Your API key (e.g., `sk-ant-api03-...`)

   **Option 2: Combined file**
   - Create document: `API_CREDENTIALS.json`
   - Content:
     ```json
     {
       "anthropic_api_key": "sk-ant-api03-..."
     }
     ```

   Get your API key: https://console.anthropic.com/settings/keys

Installation check:
```bash
python3 -c "import anthropic; print(f'✓ anthropic {anthropic.__version__}')"
```

## Error Handling

The module provides comprehensive error handling:

```python
from claude_client import invoke_claude, ClaudeInvocationError

try:
    response = invoke_claude("Your prompt here")
except ClaudeInvocationError as e:
    print(f"API Error: {e}")
    print(f"Status: {e.status_code}")
    print(f"Details: {e.details}")
except ValueError as e:
    print(f"Configuration Error: {e}")
```

Common errors:
- **API key missing**: Add ANTHROPIC_API_KEY.txt to project knowledge (see Setup above)
- **Rate limits**: Reduce max_workers or add delays
- **Token limits**: Reduce prompt size or max_tokens
- **Network errors**: Automatic retry with exponential backoff


## Prompt Caching

For detailed caching workflows and best practices, see [references/workflows.md](references/workflows.md#prompt-caching-workflows).

## Performance Considerations

**Token efficiency:**
- Parallel calls use more tokens but save wall-clock time
- Use prompt caching for shared context (90% cost reduction)
- Use concise system prompts to reduce overhead
- Consider token budgets when setting max_tokens

**Rate limits:**
- Anthropic API has per-minute rate limits
- Default max_workers=5 is safe for most tiers
- Adjust based on your API tier and rate limits

**Cost management:**
- Each invocation consumes API credits
- Monitor usage in Anthropic Console
- Use smaller models (haiku) for simple tasks
- Use prompt caching for repeated context (90% savings)
- Cache lifetime: 5 minutes, refreshed on each use

## Best Practices

1. **Use parallel invocations for independent tasks only**
   - Don't parallelize sequential dependencies
   - Each parallel task should be self-contained

2. **Set appropriate system prompts**
   - Define clear roles/expertise for each instance
   - Keeps responses focused and relevant

3. **Handle errors gracefully**
   - Always wrap invocations in try-except
   - Provide fallback behavior for failures

4. **Test with small batches first**
   - Verify prompts work before scaling
   - Check token usage and costs

5. **Consider alternatives**
   - Not all tasks benefit from multiple instances
   - Sometimes sequential with context is better

## Token Efficiency

This skill uses ~800 tokens when loaded but enables powerful multi-agent patterns that can dramatically improve complex analysis quality and speed.

## See Also

- [references/function-reference.md](references/function-reference.md) - Full signatures for every function this skill exposes
- [references/api-reference.md](references/api-reference.md) - Anthropic API details: models, rate limits, caching
- [references/workflows.md](references/workflows.md) - Worked orchestration examples
- [Anthropic API Docs](https://docs.anthropic.com/claude/reference) - Official documentation
