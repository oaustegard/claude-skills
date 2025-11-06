# Claude API Reference

Detailed API documentation for the invoking-claude skill.

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

## Performance Tips

1. **Batch independent calls**: Use `invoke_parallel()` for concurrent execution
2. **Use appropriate models**: Haiku for simple tasks, Sonnet for complex
3. **Cache common results**: Store responses for repeated prompts
4. **Optimize prompts**: Shorter prompts = less cost + faster response
5. **Set reasonable max_tokens**: Don't request more than needed
6. **Handle errors gracefully**: Implement retry logic with backoff

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
