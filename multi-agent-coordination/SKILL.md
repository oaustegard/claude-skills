---
name: multi-agent-coordination
description: Orchestrate parallel Claude instances, delegated sub-tasks, and multi-agent workflows with streaming and tool-enabled agent delegation. Use for parallel analysis, multi-perspective reviews, or complex task decomposition.
---

# Invoking Claude Programmatically

This skill enables programmatic invocation of Claude via the Anthropic API for advanced workflows including parallel processing, task delegation, and multi-agent analysis.

## When to Use This Skill

**Primary use cases:**
- **Parallel sub-tasks**: Break complex analysis into simultaneous independent streams
- **Multi-perspective analysis**: Get 3-5 different expert viewpoints concurrently
- **Delegation**: Offload specific subtasks to specialized Claude instances
- **Recursive workflows**: Claude coordinating multiple Claude instances
- **High-volume processing**: Batch process multiple items concurrently

**Trigger patterns:**
- "Invoke Claude to analyze..."
- "Ask another Claude instance..."
- "Run parallel analyses from different perspectives..."
- "Delegate this subtask to..."
- "Get expert opinions from multiple angles..."

## Quick Start

### Single Invocation

```python
import sys
sys.path.append('/home/user/claude-skills/multi-agent-coordination/scripts')
from claude_client import invoke_claude

response = invoke_claude(
    prompt="Analyze this code for security vulnerabilities: ...",
    model="claude-sonnet-4-5-20250929"
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

results = invoke_parallel(prompts, model="claude-sonnet-4-5-20250929")

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

### `invoke_claude()`

Single synchronous invocation with full control:

```python
invoke_claude(
    prompt: str | list[dict],
    model: str = "claude-sonnet-4-5-20250929",
    system: str | list[dict] | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    streaming: bool = False,
    cache_system: bool = False,
    cache_prompt: bool = False,
    messages: list[dict] | None = None,
    **kwargs
) -> str
```

**Parameters:**
- `prompt`: The user message (string or list of content blocks)
- `model`: Claude model to use (default: claude-sonnet-4-5-20250929)
- `system`: Optional system prompt (string or list of content blocks)
- `max_tokens`: Maximum tokens in response (default: 4096)
- `temperature`: Randomness 0-1 (default: 1.0)
- `streaming`: Enable streaming response (default: False)
- `cache_system`: Add cache_control to system prompt (requires 1024+ tokens, default: False)
- `cache_prompt`: Add cache_control to user prompt (requires 1024+ tokens, default: False)
- `messages`: Pre-built messages list for multi-turn (overrides prompt)
- `**kwargs`: Additional API parameters (top_p, top_k, etc.)

**Returns:** Response text as string

**Note:** Caching requires minimum 1,024 tokens per cache breakpoint. Cache lifetime is 5 minutes (refreshed on use).

### `invoke_parallel()`

Concurrent invocations using lightweight workflow pattern:

```python
invoke_parallel(
    prompts: list[dict],
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: str | list[dict] | None = None,
    cache_shared_system: bool = False
) -> list[str]
```

**Parameters:**
- `prompts`: List of dicts with 'prompt' (required) and optional 'system', 'temperature', 'cache_system', 'cache_prompt', etc.
- `model`: Claude model for all invocations
- `max_tokens`: Max tokens per response
- `max_workers`: Max concurrent API calls (default: 5, max: 10)
- `shared_system`: System context shared across ALL invocations (for cache efficiency)
- `cache_shared_system`: Add cache_control to shared_system (default: False)

**Returns:** List of response strings in same order as prompts

**Note:** For optimal cost savings, put large common context (1024+ tokens) in `shared_system` with `cache_shared_system=True`. First invocation creates cache, subsequent ones reuse it (90% cost reduction).

### `invoke_claude_streaming()`

Stream responses in real-time with optional callbacks:

```python
invoke_claude_streaming(
    prompt: str | list[dict],
    callback: callable = None,
    model: str = "claude-sonnet-4-5-20250929",
    system: str | list[dict] | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    cache_system: bool = False,
    cache_prompt: bool = False,
    **kwargs
) -> str
```

**Parameters:**
- `callback`: Optional function called with each text chunk (str) as it arrives
- (other parameters same as invoke_claude)

**Returns:** Complete accumulated response text

### `invoke_parallel_streaming()`

Parallel invocations with per-agent streaming callbacks:

```python
invoke_parallel_streaming(
    prompts: list[dict],
    callbacks: list[callable] = None,
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: str | list[dict] | None = None,
    cache_shared_system: bool = False
) -> list[str]
```

**Parameters:**
- `callbacks`: Optional list of callback functions, one per prompt
- (other parameters same as invoke_parallel)

### `invoke_parallel_interruptible()`

Parallel invocations with cancellation support:

```python
invoke_parallel_interruptible(
    prompts: list[dict],
    interrupt_token: InterruptToken = None,
    # ... same other parameters as invoke_parallel
) -> list[str]
```

**Parameters:**
- `interrupt_token`: Optional InterruptToken to signal cancellation
- (other parameters same as invoke_parallel)

**Returns:** List of response strings (None for interrupted tasks)

### `ConversationThread`

Manages multi-turn conversations with automatic caching:

```python
thread = ConversationThread(
    system: str | list[dict] | None = None,
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    temperature: float = 1.0,
    cache_system: bool = True
)

response = thread.send(
    user_message: str | list[dict],
    cache_history: bool = True
) -> str
```

**Methods:**
- `send(message, cache_history=True)`: Send message and get response
- `get_messages()`: Get conversation history
- `clear()`: Clear conversation history
- `__len__()`: Get number of turns

**Note:** Automatically caches conversation history to minimize token costs across turns.

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

# Main Claude delegates subtasks
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
Main Claude (this skill)
    ↓
Orchestrator Logic
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

## Dependencies

This skill requires:
- `anthropic` Python library (install: `pip install anthropic`)
- `api-credentials` skill for API key management

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
- **API key missing**: See api-credentials skill setup
- **Rate limits**: Reduce max_workers or add delays
- **Token limits**: Reduce prompt size or max_tokens
- **Network errors**: Automatic retry with exponential backoff

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

- [api-credentials skill](../api-credentials/SKILL.md) - Required dependency
- [references/api-reference.md](references/api-reference.md) - Detailed API documentation
- [Anthropic API Docs](https://docs.anthropic.com/claude/reference) - Official documentation
