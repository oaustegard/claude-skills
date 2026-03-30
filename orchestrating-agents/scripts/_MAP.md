# scripts/
*Files: 7*

## Files

### claude_client.py
> Imports: `json, os, time, threading, pathlib`...
- **get_anthropic_api_key** (f) `()` :26
- **ClaudeInvocationError** (C) :110
  - **__init__** (m) `(self, message: str, status_code: int = None, details: Any = None)` :112
- **invoke_claude** (f) `(
    prompt: Union[str, list[dict]],
    model: str = "claude-sonnet-4-6",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    streaming: bool = False,
    cache_system: bool = False,
    cache_prompt: bool = False,
    messages: list[dict] | None = None,
    **kwargs
)` :199
- **invoke_claude_streaming** (f) `(
    prompt: Union[str, list[dict]],
    callback: callable = None,
    model: str = "claude-sonnet-4-6",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    cache_system: bool = False,
    cache_prompt: bool = False,
    **kwargs
)` :329
- **invoke_parallel** (f) `(
    prompts: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
)` :408
- **invoke_parallel_streaming** (f) `(
    prompts: list[dict],
    callbacks: list[callable] = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
)` :537
- **StallDetector** (C) :609
  - **__init__** (m) `(self, timeout: float = 60.0, on_stall: callable = None)` :622
  - **register** (m) `(self, task_id: str)` :630
  - **heartbeat** (m) `(self, task_id: str)` :635
  - **unregister** (m) `(self, task_id: str)` :641
  - **check_stalled** (m) `(self)` :646
  - **start_monitoring** (m) `(self, poll_interval: float = 5.0)` :662
  - **stop_monitoring** (m) `(self)` :685
- **InterruptToken** (C) :694
  - **__init__** (m) `(self)` :696
  - **interrupt** (m) `(self)` :699
  - **is_interrupted** (m) `(self)` :703
  - **reset** (m) `(self)` :707
- **invoke_parallel_interruptible** (f) `(
    prompts: list[dict],
    interrupt_token: InterruptToken = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
)` :712
- **ConversationThread** (C) :789
  - **__init__** (m) `(
        self,
        system: Union[str, list[dict], None] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        cache_system: bool = True,
        max_turns: int | None = None,
        continuation_prompt: str | None = None
    )` :801
  - **send** (m) `(self, user_message: Union[str, list[dict]], cache_history: bool = True)` :835
  - **send_continuation** (m) `(
        self,
        guidance: str | None = None,
        cache_history: bool = True
    )` :889
  - **get_messages** (m) `(self)` :924
  - **clear** (m) `(self)` :928
  - **__len__** (m) `(self)` :932
- **get_available_models** (f) `()` :937
- **parse_json_response** (f) `(raw: str)` :954
- **invoke_claude_json** (f) `(
    prompt: Union[str, list[dict]],
    model: str = "claude-sonnet-4-6",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    cache_system: bool = False,
    cache_prompt: bool = False,
    messages: list[dict] | None = None,
    **kwargs
)` :980

### orchestration.py
> Imports: `time, threading, typing, concurrent.futures, claude_client`...
- **compute_backoff_delay** (f) `(
    attempt: int,
    *,
    is_continuation: bool = False,
    base_ms: float = 1000.0,
    max_ms: float = 10000.0,
)` :31
- **invoke_with_retry** (f) `(
    prompt: Union[str, list[dict]],
    *,
    max_retries: int = 3,
    base_delay_ms: float = 1000.0,
    max_delay_ms: float = 10000.0,
    is_continuation: bool = False,
    model: str = "claude-sonnet-4-6",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    **kwargs,
)` :60
- **invoke_parallel_with_reconciliation** (f) `(
    prompts: list[dict],
    *,
    reconcile: Optional[Callable[[list[dict], "TaskTracker"], list[dict]]] = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False,
    max_retries: int = 3,
    stall_timeout: Optional[float] = None,
    on_stall: Optional[Callable] = None,
)` :129
- **ConcurrencyLimiter** (C) :297
  - **__init__** (m) `(
        self,
        global_limit: int = 10,
        category_limits: Optional[dict[str, int]] = None,
    )` :310
  - **_get_category_semaphore** (m) `(self, category: Optional[str])` :323
  - **acquire** (m) `(self, category: Optional[str] = None, timeout: float = None)` :332
  - **release** (m) `(self, category: Optional[str] = None)` :354
- **invoke_parallel_managed** (f) `(
    prompts: list[dict],
    *,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False,
    max_retries: int = 3,
    reconcile: Optional[Callable] = None,
    concurrency_limiter: Optional[ConcurrencyLimiter] = None,
    stall_timeout: Optional[float] = None,
    on_stall: Optional[Callable] = None,
)` :362

### task_state.py
> Imports: `enum, threading, time, typing`
- **TaskState** (C) :21
- **InvalidTransitionError** (C) :46
  - **__init__** (m) `(self, task_id: str, current: TaskState, target: TaskState)` :48
- **TaskInfo** (C) :57
  - **__init__** (m) `(self, task_id: str, state: TaskState, attempt: int,
                 created_at: float, updated_at: float,
                 category: Optional[str], metadata: Optional[dict])` :62
  - **__repr__** (m) `(self)` :73
- **TaskTracker** (C) :103
  - **__init__** (m) `(self, max_retries: int = 3)` :114
  - **add** (m) `(self, task_id: str, category: Optional[str] = None,
            metadata: Optional[dict] = None)` :119
  - **transition** (m) `(self, task_id: str, target: TaskState)` :142
  - **claim** (m) `(self, task_id: str)` :172
  - **start** (m) `(self, task_id: str)` :176
  - **complete** (m) `(self, task_id: str)` :180
  - **fail** (m) `(self, task_id: str, error: Optional[str] = None)` :184
  - **retry** (m) `(self, task_id: str)` :205
  - **cancel** (m) `(self, task_id: str)` :233
  - **get** (m) `(self, task_id: str)` :237
  - **get_by_state** (m) `(self, state: TaskState)` :242
  - **get_by_category** (m) `(self, category: str)` :250
  - **active_count** (m) `(self, category: Optional[str] = None)` :258
  - **is_all_terminal** (m) `(self)` :272
  - **summary** (m) `(self)` :279
  - **__len__** (m) `(self)` :288
  - **__contains__** (m) `(self, task_id: str)` :292

### test_caching.py
> Imports: `sys, pathlib, claude_client`
- **test_cache_system** (f) `()` :14
- **test_cache_prompt** (f) `()` :31
- **test_shared_system_parallel** (f) `()` :47
- **test_conversation_thread** (f) `()` :74
- **test_manual_cache_blocks** (f) `()` :99

### test_integration.py
> Imports: `sys, pathlib, claude_client`
- **test_simple_invocation** (f) `()` :28
- **test_parallel_analysis** (f) `()` :46
- **test_error_handling** (f) `()` :108
- **test_streaming** (f) `()` :155
- **test_parallel_streaming** (f) `()` :174
- **test_interruptible** (f) `()` :193
- **test_credentials_fallback** (f) `()` :213
- **main** (f) `()` :245

### test_interrupt.py
> Imports: `sys, pathlib, threading, time, claude_client`
- **test_interrupt** (f) `()` :12

### test_streaming.py
> Imports: `sys, pathlib, claude_client`
- **test_basic_streaming** (f) `()` :10
- **test_parallel_streaming** (f) `()` :30

