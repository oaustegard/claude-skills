# Claude API Reference

Detailed API documentation for the orchestrating-agents skill.

## API Models

### Available Models (as of 2025)

| Model | Description | Max Tokens | Best For |
|-------|-------------|------------|----------|
| claude-sonnet-4-5-20250929 | Latest Sonnet 4.5 | 8192 | Balanced performance/cost |
| claude-sonnet-4-20250514 | Sonnet 4 | 8192 | Complex reasoning |
| claude-opus-4-20250514 | Opus 4 | 8192 | Highest capability |
| claude-3-5-sonnet-20241022 | Claude 3.5 Sonnet | 8192 | Legacy support |
| claude-3-5-haiku-20241022 | Claude 3.5 Haiku | 8192 | Fast, cost-effective |

## Rate Limits

Rate limits vary by API tier:

| Tier | Requests/min | Tokens/min | Concurrent |
|------|--------------|------------|------------|
| Free | 5 | 50,000 | 1 |
| Build | 50 | 100,000 | 5 |
| Scale | Custom | Custom | Custom |

**Note:** Use `max_workers` parameter in `invoke_parallel()` to respect your tier's concurrent limit.

## Error Codes

### HTTP Status Codes

- **400 Bad Request**: Invalid parameters (check prompt, max_tokens, etc.)
- **401 Unauthorized**: Invalid API key
- **403 Forbidden**: API key lacks permissions
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Anthropic service issue
- **529 Overloaded**: Service temporarily overloaded

### Error Handling Pattern

```python
from claude_client import invoke_claude, ClaudeInvocationError
import time

def invoke_with_retry(prompt, max_retries=3):
    """Invoke with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            return invoke_claude(prompt)
        except ClaudeInvocationError as e:
            if e.status_code == 429 and attempt < max_retries - 1:
                wait = 2 ** attempt  # Exponential backoff
                print(f"Rate limited, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
```

## Advanced Parameters

### System Prompts

System prompts set context and behavior:

```python
invoke_claude(
    prompt="Analyze this code...",
    system="You are an expert security auditor. Focus on vulnerabilities."
)
```

**Best practices:**
- Keep system prompts concise (50-200 tokens)
- Define specific expertise or perspective
- Avoid redundant instructions

### Temperature

Controls randomness (0.0-1.0):

```python
invoke_claude(
    prompt="Generate creative story ideas",
    temperature=0.9  # More creative/random
)

invoke_claude(
    prompt="Calculate the result",
    temperature=0.1  # More deterministic
)
```

**Guidelines:**
- **0.0-0.3**: Deterministic tasks (math, code, structured output)
- **0.4-0.7**: Balanced (general analysis, Q&A)
- **0.8-1.0**: Creative tasks (brainstorming, writing)

### Streaming

Enable streaming for real-time output:

```python
response = invoke_claude(
    prompt="Write a long essay about...",
    streaming=True  # Prints as it generates
)
```

**Use streaming when:**
- Response is long (>500 tokens)
- User needs immediate feedback
- Building interactive experiences

**Don't use streaming when:**
- Programmatically processing response
- Running parallel invocations
- Batching multiple calls

## Parallel Invocation Patterns

### Pattern 1: Map-Reduce

Process multiple items, then synthesize:

```python
# Map: Analyze each item
items = ["item1", "item2", "item3"]
analyses = invoke_parallel([
    {"prompt": f"Analyze: {item}"} for item in items
])

# Reduce: Synthesize results
synthesis = invoke_claude(
    "Synthesize these analyses:\n" + "\n".join(analyses)
)
```

### Pattern 2: Multi-Expert Consensus

Get multiple perspectives and find consensus:

```python
experts = [
    {"prompt": prompt, "system": "Security expert"},
    {"prompt": prompt, "system": "Performance expert"},
    {"prompt": prompt, "system": "UX expert"}
]
perspectives = invoke_parallel(experts)

# Find consensus
consensus = invoke_claude(
    f"Find consensus among these perspectives:\n{perspectives}"
)
```

### Pattern 3: Speculative Execution

Try multiple approaches, pick best:

```python
approaches = [
    {"prompt": "Solve using approach A: ..."},
    {"prompt": "Solve using approach B: ..."},
    {"prompt": "Solve using approach C: ..."}
]
solutions = invoke_parallel(approaches)

# Evaluate and pick best
best = invoke_claude(
    f"Which solution is best and why?\n{solutions}"
)
```

## Token Estimation

Rough token counts:
- 1 token ≈ 4 characters
- 1 token ≈ 0.75 words
- 100 tokens ≈ 75 words

**Estimating costs:**
```python
prompt_tokens = len(prompt) // 4
max_response_tokens = max_tokens
total_tokens = prompt_tokens + max_response_tokens
```

## Prompt Caching

### Overview

Prompt caching enables reusing large portions of prompts across multiple API calls, reducing costs by up to 90% and latency by up to 85% for cached content.

### How It Works

- **Cache Key**: Generated from cryptographic hash of prompt content up to cache breakpoint
- **Cache Lifetime**: 5 minutes (default), refreshed on each use
- **Cache Sharing**: Organization-scoped (same org can share cache with identical prompts)
- **Cache Breakpoints**: Up to 4 per request
- **Minimum Size**: 1,024 tokens per cache breakpoint

### API Structure

#### Cached System Prompt

```python
# String (auto-converted with cache_system=True)
invoke_claude(
    prompt="Your question...",
    system="Large system instructions...",
    cache_system=True
)

# Or manual content blocks
system_blocks = [
    {"type": "text", "text": "Base instructions..."},
    {"type": "text", "text": "Large context...", "cache_control": {"type": "ephemeral"}}
]
invoke_claude(prompt="Your question...", system=system_blocks)
```

#### Cached User Prompt

```python
# Large document with question
prompt_blocks = [
    {"type": "text", "text": "<document>...</document>", "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": "What are the key points?"}
]
invoke_claude(prompt=prompt_blocks)

# Or use cache_prompt=True for simple string
invoke_claude(
    prompt="Large text...",
    cache_prompt=True
)
```

#### Multi-Turn with Caching

```python
from claude_client import ConversationThread

thread = ConversationThread(
    system="Large base context...",
    cache_system=True  # Caches system prompt
)

# Each turn caches full history
response1 = thread.send("First question")
response2 = thread.send("Follow-up question")  # Reuses cached system + turn 1
```

### Cost Analysis

**Without Caching** (10 parallel agents, 10K shared context):
- Input tokens: 10 × 10,000 = 100,000 tokens
- Cost (Sonnet 4.5): 100K × $3/MTok = $3.00

**With Caching** (same scenario):
- First agent: 10,000 tokens (full price) = $0.30
- Agents 2-10: 9 × (10,000 × 0.1) = 9,000 tokens (cache hits) = $0.027
- Total: $0.327 (89% savings)

### Cache Efficiency Patterns

#### Pattern 1: Shared Context in Parallel

```python
# Optimal: All agents share cached base context
invoke_parallel(
    prompts=[...],
    shared_system="<large_context>...</large_context>",
    cache_shared_system=True
)
```

#### Pattern 2: Multi-Turn Conversations

```python
# Each turn builds on cached history
thread = ConversationThread(system="...", cache_system=True)
for question in questions:
    response = thread.send(question)  # Cumulative caching
```

#### Pattern 3: Mixed Orchestration

```python
# Orchestrator caches base context
base = "<codebase>...</codebase>"

# Parallel analysis (shares cache)
analyses = invoke_parallel(
    prompts=[...],
    shared_system=base,
    cache_shared_system=True
)

# Follow-up threads (reuse same cached base)
agent1 = ConversationThread(system=base, cache_system=True)
agent2 = ConversationThread(system=base, cache_system=True)
```

### Caching Limitations

1. **Minimum tokens**: Each cache breakpoint requires 1,024+ tokens
2. **Maximum breakpoints**: 4 cache breakpoints per request
3. **Exact match required**: Prompts must be IDENTICAL for cache hits (including whitespace)
4. **TTL**: 5-minute cache lifetime (can be extended with 1-hour option)
5. **Organization-scoped**: Cache not shared across different organizations

### Token Usage Reporting

API responses include caching metrics in usage field:

```python
{
    "usage": {
        "input_tokens": 1024,
        "cache_creation_input_tokens": 10000,  # Tokens written to cache
        "cache_read_input_tokens": 9500,       # Tokens read from cache
        "output_tokens": 256
    }
}
```

## Streaming Functions

### `invoke_claude_streaming()`

Stream responses in real-time with callback support:

```python
from claude_client import invoke_claude_streaming

def progress_callback(chunk):
    print(chunk, end='', flush=True)

response = invoke_claude_streaming(
    prompt="Write a comprehensive analysis...",
    callback=progress_callback,
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096
)
```

**Use cases:**
- Real-time user feedback
- Long-running analyses
- Interactive applications

### `invoke_parallel_streaming()`

Parallel invocations with per-agent streaming:

```python
from claude_client import invoke_parallel_streaming

callbacks = [
    lambda chunk: print(f"[Agent1] {chunk}", end=''),
    lambda chunk: print(f"[Agent2] {chunk}", end=''),
]

results = invoke_parallel_streaming(
    [
        {"prompt": "Analyze security..."},
        {"prompt": "Analyze performance..."}
    ],
    callbacks=callbacks
)
```

### `invoke_parallel_interruptible()`

Parallel invocations with cancellation:

```python
from claude_client import invoke_parallel_interruptible, InterruptToken
import threading

token = InterruptToken()

# Run in background
def run_tasks():
    return invoke_parallel_interruptible(
        prompts=[...],
        interrupt_token=token
    )

thread = threading.Thread(target=run_tasks)
thread.start()

# Cancel if needed
token.interrupt()
```

## Performance Tips

1. **Batch independent calls**: Use `invoke_parallel()` for concurrent execution
2. **Use prompt caching**: For shared context or multi-turn (90% cost reduction)
3. **Use appropriate models**: Haiku for simple tasks, Sonnet for complex
4. **Optimize prompts**: Shorter prompts = less cost + faster response
5. **Set reasonable max_tokens**: Don't request more than needed
6. **Handle errors gracefully**: Implement retry logic with backoff
7. **Monitor cache hits**: Check usage metrics to verify caching effectiveness
8. **Use streaming for long responses**: Provides immediate feedback to users

## Security Considerations

1. **API Key Security**
   - Never hardcode API keys
   - Use api-credentials skill or environment variables
   - Rotate keys regularly

2. **Input Validation**
   - Sanitize user inputs before sending to API
   - Validate prompt length to avoid token limit errors
   - Check for sensitive data in prompts

3. **Rate Limiting**
   - Respect API tier limits
   - Implement client-side rate limiting
   - Monitor usage in Anthropic Console

4. **Error Handling**
   - Don't expose API errors to end users
   - Log errors for debugging
   - Provide user-friendly error messages

## Further Reading

- [Anthropic API Documentation](https://docs.anthropic.com/claude/reference)
- [Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook)
- [API Migration Guide](https://docs.anthropic.com/claude/reference/migrating)
