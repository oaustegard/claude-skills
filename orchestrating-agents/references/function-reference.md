# Function Reference

Complete signatures and usage for every function the `orchestrating-agents`
skill exposes. Extracted from SKILL.md to keep the always-loaded surface small;
read this when you need exact parameters or return shapes.

### `invoke_claude()`

Single synchronous invocation with full control:

```python
invoke_claude(
    prompt: str | list[dict],
    model: str = "claude-sonnet-4-6",
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
- `model`: Claude model to use (default: claude-sonnet-4-6)
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
    model: str = "claude-sonnet-4-6",
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
    model: str = "claude-sonnet-4-6",
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
    model: str = "claude-sonnet-4-6",
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
    model: str = "claude-sonnet-4-6",
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

**New in 0.3.0:**
- `turn_count` property: Number of completed turn pairs
- `send_continuation(guidance, cache_history)`: Lightweight continuation turn (requires prior `send()`)
- `max_turns` constructor parameter: Optional turn limit
- `continuation_prompt` constructor parameter: Default continuation guidance

### `StallDetector`

Monitors activity timestamps and detects unresponsive operations:

```python
from claude_client import StallDetector

def handle_stall(task_id, idle_seconds):
    print(f"Task {task_id} stalled for {idle_seconds:.1f}s")

detector = StallDetector(timeout=60.0, on_stall=handle_stall)
detector.register("task-1")
detector.start_monitoring(poll_interval=5.0)

# Call heartbeat() during streaming/progress
detector.heartbeat("task-1")

# When done
detector.unregister("task-1")
detector.stop_monitoring()
```

### `TaskTracker` (task_state module)

Formal task lifecycle state machine with enforced transitions:

```python
from task_state import TaskTracker, TaskState

tracker = TaskTracker(max_retries=3)
tracker.add("task-1", category="security")

tracker.claim("task-1")    # UNCLAIMED → CLAIMED
tracker.start("task-1")    # CLAIMED → RUNNING (increments attempt)
tracker.complete("task-1")  # RUNNING → COMPLETED

# On failure with retry:
tracker.fail("task-2", error="timeout")
tracker.retry("task-2")     # FAILED → RETRY_QUEUED (if under max_retries)
tracker.claim("task-2")     # RETRY_QUEUED → CLAIMED

# Query state
tracker.active_count(category="security")
tracker.get_by_state(TaskState.RUNNING)
tracker.summary()  # {"completed": 1, "running": 1, ...}
```

### `invoke_with_retry()` (orchestration module)

Single invocation with exponential backoff:

```python
from orchestration import invoke_with_retry

response = invoke_with_retry(
    "Analyze this code...",
    max_retries=3,
    base_delay_ms=1000,   # 1s, 2s, 4s backoff
    max_delay_ms=10000,   # capped at 10s
)
```

### `invoke_parallel_managed()` (orchestration module)

Full-featured parallel invocations with all Symphony patterns:

```python
from orchestration import invoke_parallel_managed, ConcurrencyLimiter

limiter = ConcurrencyLimiter(
    global_limit=10,
    category_limits={"security": 3, "perf": 3}
)

def reconcile(prompts, tracker):
    # Filter out invalid/duplicate work before dispatch
    return [p for p in prompts if should_run(p)]

results = invoke_parallel_managed(
    prompts=[
        {"prompt": "Security review...", "task_id": "sec-1", "category": "security"},
        {"prompt": "Perf review...", "task_id": "perf-1", "category": "perf"},
    ],
    reconcile=reconcile,
    concurrency_limiter=limiter,
    max_retries=3,
    stall_timeout=60.0,
    on_stall=lambda tid, idle: print(f"{tid} stalled"),
)
```
