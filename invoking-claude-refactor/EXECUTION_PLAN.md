# Execution Plan: Multi-Agent Coordination Skill Enhancement

## Objective
Enhance the `invoking-claude` skill with streaming, interrupt support, and agent delegation patterns inspired by the WebSocket Agent SDK architecture.

## Phase 1: Rename and Restructure

### 1.1 Rename Skill Directory
**Current:** `/tmp/invoking-claude/`  
**New:** `/tmp/multi-agent-coordination/`

```bash
cd /tmp
mv invoking-claude multi-agent-coordination
cd multi-agent-coordination
```

### 1.2 Update Skill Metadata
**File:** `SKILL.md` (lines 1-4)

```yaml
---
name: multi-agent-coordination
description: Orchestrate parallel Claude instances, delegated sub-tasks, and multi-agent workflows with streaming and tool-enabled agent delegation. Use for parallel analysis, multi-perspective reviews, or complex task decomposition.
---
```

### 1.3 Update Internal References
**Files to update:**
- `SKILL.md`: Replace `invoking-claude` → `multi-agent-coordination` in all paths
- `scripts/claude_client.py`: Update module docstring
- `scripts/test_*.py`: Update import paths

## Phase 2: Add Streaming Support

### 2.1 Create Streaming Function
**File:** `scripts/claude_client.py`  
**Location:** After `invoke_claude()` function (around line 200)

```python
def invoke_claude_streaming(
    prompt: Union[str, list[dict]],
    callback: callable = None,
    model: str = "claude-sonnet-4-5-20250929",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    cache_system: bool = False,
    cache_prompt: bool = False,
    **kwargs
) -> str:
    """
    Invoke Claude with streaming response.
    
    Args:
        prompt: User message
        callback: Optional function called with each chunk (str) as it arrives
        model: Claude model identifier
        system: Optional system prompt
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature (0-1)
        cache_system: Add cache_control to system (requires 1024+ tokens)
        cache_prompt: Add cache_control to user prompt (requires 1024+ tokens)
        **kwargs: Additional API parameters
        
    Returns:
        Complete accumulated response text
        
    Example:
        def print_chunk(chunk):
            print(chunk, end='', flush=True)
            
        response = invoke_claude_streaming(
            "Write a story",
            callback=print_chunk
        )
    """
    api_key = get_anthropic_api_key()
    if not api_key:
        raise ClaudeInvocationError("Anthropic API key not found")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Format system and messages
    formatted_system = _format_system_with_cache(system, cache_system)
    messages = _build_messages(prompt, cache_prompt)
    
    accumulated_text = ""
    
    try:
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=formatted_system,
            messages=messages,
            **kwargs
        ) as stream:
            for text in stream.text_stream:
                accumulated_text += text
                if callback:
                    callback(text)
                    
        return accumulated_text
        
    except anthropic.APIError as e:
        raise ClaudeInvocationError(
            f"Anthropic API error: {str(e)}",
            status_code=getattr(e, 'status_code', None),
            details=getattr(e, 'response', None)
        )
    except Exception as e:
        raise ClaudeInvocationError(f"Unexpected error: {str(e)}")


def _build_messages(
    prompt: Union[str, list[dict]],
    cache_prompt: bool = False
) -> list[dict]:
    """Build messages list from prompt with optional caching."""
    content = _format_message_with_cache(prompt, cache_prompt)
    return [{"role": "user", "content": content}]
```

### 2.2 Add Parallel Streaming Support
**File:** `scripts/claude_client.py`  
**Location:** After `invoke_parallel()` function

```python
def invoke_parallel_streaming(
    prompts: list[dict],
    callbacks: list[callable] = None,
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
) -> list[str]:
    """
    Parallel invocations with streaming callbacks for each sub-agent.
    
    Args:
        prompts: List of prompt dicts (same format as invoke_parallel)
        callbacks: Optional list of callback functions, one per prompt
        model: Claude model identifier
        max_tokens: Max tokens per response
        max_workers: Max concurrent invocations
        shared_system: System context shared across all invocations
        cache_shared_system: Cache the shared_system
        
    Returns:
        List of complete response strings
        
    Example:
        callbacks = [
            lambda chunk: print(f"[Agent 1] {chunk}", end=''),
            lambda chunk: print(f"[Agent 2] {chunk}", end=''),
        ]
        
        results = invoke_parallel_streaming(
            [{"prompt": "Analyze X"}, {"prompt": "Analyze Y"}],
            callbacks=callbacks
        )
    """
    if callbacks and len(callbacks) != len(prompts):
        raise ValueError("callbacks list must match prompts list length")
    
    formatted_shared = _format_system_with_cache(shared_system, cache_shared_system)
    
    def process_single(idx: int, prompt_config: dict) -> tuple[int, str]:
        system = prompt_config.get('system', formatted_shared)
        callback = callbacks[idx] if callbacks else None
        
        result = invoke_claude_streaming(
            prompt=prompt_config['prompt'],
            callback=callback,
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=prompt_config.get('temperature', 1.0),
            cache_system=prompt_config.get('cache_system', False),
            cache_prompt=prompt_config.get('cache_prompt', False)
        )
        return (idx, result)
    
    results = [None] * len(prompts)
    
    with ThreadPoolExecutor(max_workers=min(max_workers, 10)) as executor:
        futures = {
            executor.submit(process_single, i, config): i 
            for i, config in enumerate(prompts)
        }
        
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result
    
    return results
```

## Phase 3: Add Interrupt Support

### 3.1 Add Interrupt Mechanism
**File:** `scripts/claude_client.py`  
**Location:** After streaming functions

```python
import threading

class InterruptToken:
    """Thread-safe interrupt flag for cancelling operations."""
    def __init__(self):
        self._interrupted = threading.Event()
    
    def interrupt(self):
        """Signal interruption."""
        self._interrupted.set()
    
    def is_interrupted(self) -> bool:
        """Check if interrupted."""
        return self._interrupted.is_set()
    
    def reset(self):
        """Reset interrupt flag."""
        self._interrupted.clear()


def invoke_parallel_interruptible(
    prompts: list[dict],
    interrupt_token: InterruptToken = None,
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
) -> list[str]:
    """
    Parallel invocations with interrupt support.
    
    Args:
        prompts: List of prompt dicts
        interrupt_token: Optional InterruptToken to signal cancellation
        (other args same as invoke_parallel)
        
    Returns:
        List of response strings (None for interrupted tasks)
        
    Example:
        token = InterruptToken()
        
        # In another thread or after delay:
        # token.interrupt()
        
        results = invoke_parallel_interruptible(
            prompts,
            interrupt_token=token
        )
    """
    if interrupt_token is None:
        interrupt_token = InterruptToken()
    
    formatted_shared = _format_system_with_cache(shared_system, cache_shared_system)
    
    def process_single_with_check(idx: int, config: dict) -> tuple[int, str]:
        if interrupt_token.is_interrupted():
            return (idx, None)
        
        system = config.get('system', formatted_shared)
        
        # Note: Anthropic API doesn't support mid-request cancellation
        # This checks before starting each request
        result = invoke_claude(
            prompt=config['prompt'],
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=config.get('temperature', 1.0),
            cache_system=config.get('cache_system', False),
            cache_prompt=config.get('cache_prompt', False)
        )
        return (idx, result)
    
    results = [None] * len(prompts)
    
    with ThreadPoolExecutor(max_workers=min(max_workers, 10)) as executor:
        futures = {
            executor.submit(process_single_with_check, i, config): i 
            for i, config in enumerate(prompts)
        }
        
        for future in as_completed(futures):
            if interrupt_token.is_interrupted():
                # Cancel remaining futures
                for f in futures:
                    f.cancel()
                break
            
            idx, result = future.result()
            results[idx] = result
    
    return results
```

## Phase 4: Add Agent SDK Delegation Pattern

### 4.1 Create New Section in SKILL.md
**File:** `SKILL.md`  
**Location:** After "Example Workflows" section (around line 290)

```markdown
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
```

## Phase 5: Documentation Updates

### 5.1 Add Streaming Examples to SKILL.md
**File:** `SKILL.md`  
**Location:** After "Quick Start" section (around line 67)

```markdown
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
```

### 5.2 Update Core Functions Section
**File:** `SKILL.md`  
**Location:** In "Core Functions" section (around line 123)

Add after existing function docs:

```markdown
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
```

## Phase 6: Testing

### 6.1 Create Streaming Test
**File:** `scripts/test_streaming.py`

```python
#!/usr/bin/env python3
"""Test streaming functionality."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from claude_client import invoke_claude_streaming, invoke_parallel_streaming

def test_basic_streaming():
    """Test basic streaming with callback."""
    print("=== Test 1: Basic Streaming ===")
    
    chunks = []
    def collect_chunk(chunk):
        chunks.append(chunk)
        print(chunk, end='', flush=True)
    
    response = invoke_claude_streaming(
        "Count from 1 to 5, one number per line.",
        callback=collect_chunk
    )
    
    print(f"\n\nTotal chunks received: {len(chunks)}")
    print(f"Complete response: {response}")
    assert len(chunks) > 0
    assert response == ''.join(chunks)


def test_parallel_streaming():
    """Test parallel streaming with multiple callbacks."""
    print("\n=== Test 2: Parallel Streaming ===")
    
    def callback1(chunk):
        print(f"[Agent1] {chunk}", end='', flush=True)
    
    def callback2(chunk):
        print(f"[Agent2] {chunk}", end='', flush=True)
    
    results = invoke_parallel_streaming(
        [
            {"prompt": "Say 'Hello from agent 1'"},
            {"prompt": "Say 'Hello from agent 2'"}
        ],
        callbacks=[callback1, callback2]
    )
    
    print(f"\n\nResults: {results}")
    assert len(results) == 2


if __name__ == "__main__":
    test_basic_streaming()
    test_parallel_streaming()
    print("\n✓ All streaming tests passed")
```

### 6.2 Create Interrupt Test
**File:** `scripts/test_interrupt.py`

```python
#!/usr/bin/env python3
"""Test interrupt functionality."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import threading
import time
from claude_client import invoke_parallel_interruptible, InterruptToken

def test_interrupt():
    """Test interrupting parallel operations."""
    print("=== Test: Interrupt ===")
    
    token = InterruptToken()
    
    # Create long-running prompts
    prompts = [
        {"prompt": f"Write a long essay about topic {i}"}
        for i in range(5)
    ]
    
    def run_analysis():
        results = invoke_parallel_interruptible(
            prompts,
            interrupt_token=token
        )
        return results
    
    # Start in background
    thread = threading.Thread(target=run_analysis)
    thread.start()
    
    # Interrupt after 2 seconds
    print("Starting analysis...")
    time.sleep(2)
    print("\nInterrupting...")
    token.interrupt()
    
    thread.join(timeout=5)
    print("✓ Interrupt test completed")


if __name__ == "__main__":
    test_interrupt()
```

### 6.3 Update Integration Test
**File:** `scripts/test_integration.py`  
**Action:** Add test cases for new functions

```python
def test_streaming():
    """Test streaming functionality."""
    response = invoke_claude_streaming(
        "Say hello",
        callback=lambda c: None  # Silent callback
    )
    assert len(response) > 0

def test_parallel_streaming():
    """Test parallel streaming."""
    results = invoke_parallel_streaming([
        {"prompt": "Say hello"},
        {"prompt": "Say goodbye"}
    ])
    assert len(results) == 2

def test_interruptible():
    """Test interruptible parallel."""
    token = InterruptToken()
    results = invoke_parallel_interruptible(
        [{"prompt": "Say hello"}],
        interrupt_token=token
    )
    assert len(results) == 1
```

## Phase 7: Final Cleanup

### 7.1 Update README References
**File:** `references/api-reference.md`  
**Action:** Add documentation for new functions

### 7.2 Create Migration Guide
**File:** `MIGRATION.md`

```markdown
# Migration Guide: invoking-claude → multi-agent-coordination

## Breaking Changes
None. All existing code remains compatible.

## New Features

### 1. Streaming Support
```python
# Old (still works)
response = invoke_claude("prompt")

# New (streaming)
response = invoke_claude_streaming("prompt", callback=print)
```

### 2. Parallel Streaming
```python
results = invoke_parallel_streaming(
    prompts,
    callbacks=[callback1, callback2]
)
```

### 3. Interrupt Support
```python
token = InterruptToken()
results = invoke_parallel_interruptible(prompts, interrupt_token=token)
# Later: token.interrupt()
```

## Renamed Skill
- Old path: `.../invoking-claude/...`
- New path: `.../multi-agent-coordination/...`
- Update import paths accordingly
```

## Execution Checklist

- [ ] Phase 1: Rename and restructure
  - [ ] Rename directory
  - [ ] Update SKILL.md metadata
  - [ ] Update internal references
  
- [ ] Phase 2: Add streaming support
  - [ ] Implement invoke_claude_streaming()
  - [ ] Implement invoke_parallel_streaming()
  - [ ] Add _build_messages() helper
  
- [ ] Phase 3: Add interrupt support
  - [ ] Implement InterruptToken class
  - [ ] Implement invoke_parallel_interruptible()
  
- [ ] Phase 4: Add Agent SDK delegation pattern
  - [ ] Add new documentation section
  - [ ] Create architecture diagrams
  - [ ] Add decision matrix
  
- [ ] Phase 5: Documentation updates
  - [ ] Add streaming examples
  - [ ] Update core functions section
  - [ ] Add usage examples
  
- [ ] Phase 6: Testing
  - [ ] Create test_streaming.py
  - [ ] Create test_interrupt.py
  - [ ] Update test_integration.py
  - [ ] Run all tests
  
- [ ] Phase 7: Final cleanup
  - [ ] Update api-reference.md
  - [ ] Create MIGRATION.md
  - [ ] Verify all imports work
  - [ ] Package for deployment

## Success Criteria

1. All existing functionality preserved (backward compatible)
2. Streaming works for single and parallel invocations
3. Interrupt mechanism functions correctly
4. Documentation clearly explains Agent SDK delegation pattern
5. All tests pass
6. Skill can be loaded and used from Claude's environment

## Estimated Token Impact

- Current skill: ~800 tokens when loaded
- Enhanced skill: ~1200 tokens (additional documentation + examples)
- Trade-off justified by significant capability expansion
