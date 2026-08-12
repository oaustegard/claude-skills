---
name: orchestrating-agents
description: Orchestrates parallel API instances, delegated sub-tasks, and multi-agent workflows with streaming and tool-enabled delegation patterns. Routes by surface — native subagents in Cowork and Claude Code, httpx fan-out on claude.ai — and covers Gemini delegation via the Cloudflare AI Gateway on every surface. Use for parallel analysis, multi-perspective reviews, or complex task decomposition.
metadata:
  version: 0.6.0
---

## SURFACE ROUTING — read first

Fan-out has three possible engines. Which exist depends on where you are running.
**Pick the engine before writing any orchestration code.**

| Engine | claude.ai | Cowork | Claude Code / CCotw |
|---|:---:|:---:|:---:|
| Native subagents (`Agent` / `Task` / `Workflow`) | ✗ | ✓ | ✓ |
| Gemini via CF AI Gateway (`invoking-gemini`) | ✓ | ✓ | ✓ |
| This skill's httpx fan-out (raw Anthropic API) | ✓ | last resort | last resort |

**Primary discriminator — check the tool list, not the filesystem.** If an `Agent`,
`Task`, or `Workflow` tool is callable, native subagents exist. That single fact
decides the row. Everything below is elaboration.

### If native subagents exist (Cowork, Claude Code, CCotw)

**Use them. Do not hand-roll from this skill.** The managed runtime gives
16-concurrent / 1000-agent ceilings, an approval gate, adversarial cross-review,
and in-session resume — all of which this skill would reimplement worse. Route
model and effort per **`agent-routing`** (calibrated on 300 measured Haiku calls);
do not re-derive that here.

Cowork adds one option Claude Code doesn't: subagents can be **declared** rather
than spawned ad hoc, as `agents/*.md` in a plugin — frontmatter `name`,
`description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`,
`skills`, `memory`, `background`, `isolation: worktree`. They appear as
`plugin-name:agent-name`. Note `hooks`, `mcpServers`, and `permissionMode` are
refused in plugin agents for security, so a declared agent inherits the session's
MCP connections and cannot bring its own.

Reach back into this skill on those surfaces only for what the runtime lacks:
stall detection, or a long-lived `ConversationThread`. **Inter-agent messaging is
NOT on that list** — the runtime ships `SendMessage` and `ListAgents`, and
`AgentPool` reimplements them worse. Corrected 2026-08-12; this block previously
sent readers to `AgentPool` for messaging the runtime already provides.

#### Native inter-agent messaging — `SendMessage` / `ListAgents`

`ListAgents` discovers reachable agents; `SendMessage` delivers plain text to one
by name or id. Both reach subagents, agent-team teammates, and independent
sessions. Official docs: `code.claude.com/docs/en/cross-session-messaging`
(shipped v2.1.224, macOS and Linux).

Four measured behaviors the docs do not state. Each cost a round trip to find;
full method and verbatim receipts in `oaustegard/experiments` →
`subagent-messaging/RESULTS.md`.

- **NEVER reply using the incoming envelope's `from` attribute.** For subagents
  that value is the agent *type* (`general-purpose`), not an address, and the
  send fails with `No agent named 'general-purpose' is reachable`. Two
  same-type peers emit identical `from` values, so it cannot distinguish
  senders even in principle. Both the `SendMessage` description and the harness
  footer on every delivered message instruct otherwise. **Capture the agentId
  from the spawn result and address that.**
- **Subagents have no `ListAgents`.** `ToolSearch("select:ListAgents")` returns
  `No matching deferred tools found` — absent, not unloaded. A subagent reaches
  `"main"` and any address handed to it in its prompt, and nothing else. **The
  topology is a star through the main conversation, not a mesh: hand every peer
  its siblings' ids at spawn, or they cannot coordinate.**
- **Delivery queues and never interrupts.** The receiver reads between tool
  calls, so a peer inside a long `Bash` call is unreachable until it surfaces.
- **A send to a completed agent resumes it with full context, and the agent
  cannot tell.** Asked directly, a resumed agent reports no gap or restart
  marker. Instructions shaped as "if you were resumed, do X" never fire —
  **state the resume in the message.** Each resume replays the transcript:
  ~40k tokens for a small agent, and a measured eight-round chain ran
  199k → 324k. **Batch questions into one send.**

Contested: `anthropics/claude-code#48160` and `ruvnet/ruflo#2028` report that
subagents can receive but not originate `SendMessage`. A CCotw subagent
originated three sends successfully on 2026-08-12 with no
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` set. **Verify origination in your own
environment before designing around either claim.**

### If native subagents do NOT exist (claude.ai chat and project sessions)

Two engines, and **Gemini is the default** — see `subagent-delegation-protocol`
in ops. Use this skill's httpx fan-out when you specifically want Claude-family
output, multi-turn threads with cached history, or inter-agent messaging.

### Gemini via Cloudflare — available on every surface

Even where native subagents exist, Gemini is the right call for
mechanical-but-large work (extractions, ports, boilerplate, schema transforms)
and for a genuinely independent second opinion in a judge panel — a different
model family fails differently, which is the whole point of a panel.

Call mechanics live in **`invoking-gemini`**; do not duplicate them here. Three
things that bite:

- Pass the **explicit model string** `gemini-3.6-flash`. The `flash` alias still
  resolves to 3.5 until that plugin's model table regenerates.
- `thinking_level` is a string in `{minimal, low, medium, high}`, default
  `medium`. Set `minimal` for mechanical generation or the model silently spends
  its output budget reasoning — symptom is an empty or truncated response.
- Credentials come from the CF AI Gateway config, BYOK. Requests route through
  the gateway rather than Google directly.

### Non-negotiable on all surfaces

**Review is not delegable.** Diff security- and protocol-critical paths
line-by-line against source, run syntax/lint checks, live-test whatever is
network-testable. Delegated output ships only after your own review, regardless
of which model produced it or which engine ran it.

Cross-model review tools (`challenge`, `verify_patch`) keep their own model
config, often deliberately a Claude. This routing does not silently repoint them.

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

2. Configure the API key **as a file the shell reads directly** — never as
   something a tool call returns.

   On claude.ai the project's files are mounted at `/mnt/project`, so the key can
   be sourced without ever entering context:

   ```bash
   set -a; . /mnt/project/ANTHROPIC.env 2>/dev/null; set +a
   ```

   ⚠️ **Do not use `project_read` to fetch a credential, on any surface.** Small
   docs are returned *inline*, so the key lands in the transcript — verified
   2026-07-30: the documented "large text is written to a local file" branch does
   not fire even at 64 KB. In Cowork there is no `/mnt/project` mount at all and
   no safe read path, so the key must arrive by a route the shell can read
   (synced skill directory, or fetched by a script from the CF config store).
   Writing is safe in both directions — `project_write` with `local_path` keeps
   contents out of context — but reading is not.

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

Loading this skill costs roughly 2k tokens. On surfaces with native subagents the
routing table at the top is usually all you need — read it, spawn natively, and
skip the rest of the file.

## See Also

**Routing companions — read these before choosing an engine:**

- `agent-routing` skill — model + effort selection for **native** subagents
  (Haiku/Sonnet/Opus, cascades, verifier gates). Calibrated on measured data.
  Applies to Cowork and Claude Code; explicitly not to claude.ai.
- `invoking-gemini` skill — call mechanics for the CF AI Gateway path, model
  table, and `thinking_level` semantics.
- `subagent-delegation-protocol` (ops config) — why Gemini is the claude.ai
  default, the Sonnet fallback config, and the non-delegable-review rule.

**This skill's own internals:**

- [references/function-reference.md](references/function-reference.md) - Full signatures for every function this skill exposes
- [references/api-reference.md](references/api-reference.md) - Anthropic API details: models, rate limits, caching
- [references/workflows.md](references/workflows.md) - Worked orchestration examples
- [Anthropic API Docs](https://docs.anthropic.com/claude/reference) - Official documentation
