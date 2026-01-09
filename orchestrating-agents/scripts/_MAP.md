# scripts/
*Files: 5*

## Files

### claude_client.py
> Imports: `json, threading, pathlib, concurrent.futures, typing`...
- **get_anthropic_api_key** (f) `()`
- **ClaudeInvocationError** (C) 
  - **__init__** (m) `(self, message: str, status_code: int = None, details: Any = None)`
- **invoke_claude** (f) `(
    prompt: Union[str, list[dict]],
    model: str = "claude-sonnet-4-5-20250929",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    streaming: bool = False,
    cache_system: bool = False,
    cache_prompt: bool = False,
    messages: list[dict] | None = None,
    **kwargs
)`
- **invoke_claude_streaming** (f) `(
    prompt: Union[str, list[dict]],
    callback: callable = None,
    model: str = "claude-sonnet-4-5-20250929",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    cache_system: bool = False,
    cache_prompt: bool = False,
    **kwargs
)`
- **invoke_parallel** (f) `(
    prompts: list[dict],
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
)`
- **invoke_parallel_streaming** (f) `(
    prompts: list[dict],
    callbacks: list[callable] = None,
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
)`
- **InterruptToken** (C) 
  - **__init__** (m) `(self)`
  - **interrupt** (m) `(self)`
  - **is_interrupted** (m) `(self)`
  - **reset** (m) `(self)`
- **invoke_parallel_interruptible** (f) `(
    prompts: list[dict],
    interrupt_token: InterruptToken = None,
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
)`
- **ConversationThread** (C) 
  - **__init__** (m) `(
        self,
        system: Union[str, list[dict], None] = None,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        cache_system: bool = True
    )`
  - **send** (m) `(self, user_message: Union[str, list[dict]], cache_history: bool = True)`
  - **get_messages** (m) `(self)`
  - **clear** (m) `(self)`
  - **__len__** (m) `(self)`
- **get_available_models** (f) `()`

### test_caching.py
> Imports: `sys, pathlib, claude_client`
- **test_cache_system** (f) `()`
- **test_cache_prompt** (f) `()`
- **test_shared_system_parallel** (f) `()`
- **test_conversation_thread** (f) `()`
- **test_manual_cache_blocks** (f) `()`

### test_integration.py
> Imports: `sys, pathlib, claude_client`
- **test_simple_invocation** (f) `()`
- **test_parallel_analysis** (f) `()`
- **test_error_handling** (f) `()`
- **test_streaming** (f) `()`
- **test_parallel_streaming** (f) `()`
- **test_interruptible** (f) `()`
- **test_credentials_fallback** (f) `()`
- **main** (f) `()`

### test_interrupt.py
> Imports: `sys, pathlib, threading, time, claude_client`
- **test_interrupt** (f) `()`

### test_streaming.py
> Imports: `sys, pathlib, claude_client`
- **test_basic_streaming** (f) `()`
- **test_parallel_streaming** (f) `()`

