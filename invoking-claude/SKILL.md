---
name: invoking-claude
description: Programmatically invokes Claude API for parallel sub-tasks, delegation, and multi-agent workflows. Use when user requests "invoke Claude", "ask another instance", "parallel analysis", or when complex analysis needs multiple simultaneous perspectives.
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
sys.path.append('/home/user/claude-skills/invoking-claude/scripts')
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

## Core Functions

### `invoke_claude()`

Single synchronous invocation with full control:

```python
invoke_claude(
    prompt: str,
    model: str = "claude-sonnet-4-5-20250929",
    system: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    streaming: bool = False,
    **kwargs
) -> str
```

**Parameters:**
- `prompt`: The user message to send to Claude
- `model`: Claude model to use (default: claude-sonnet-4-5-20250929)
- `system`: Optional system prompt to set context/role
- `max_tokens`: Maximum tokens in response (default: 4096)
- `temperature`: Randomness 0-1 (default: 1.0)
- `streaming`: Enable streaming response (default: False)
- `**kwargs`: Additional API parameters (top_p, top_k, etc.)

**Returns:** Response text as string

### `invoke_parallel()`

Concurrent invocations using lightweight workflow pattern:

```python
invoke_parallel(
    prompts: list[dict],
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    max_workers: int = 5
) -> list[str]
```

**Parameters:**
- `prompts`: List of dicts with 'prompt' (required) and optional 'system', 'temperature', etc.
- `model`: Claude model for all invocations
- `max_tokens`: Max tokens per response
- `max_workers`: Max concurrent API calls (default: 5, max: 10)

**Returns:** List of response strings in same order as prompts

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

## Performance Considerations

**Token efficiency:**
- Parallel calls use more tokens but save wall-clock time
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
- Cache results when possible

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
