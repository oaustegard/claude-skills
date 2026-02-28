# scripts/
*Files: 5*

## Files

### claude_client.py
> Imports: `json, os, threading, pathlib, concurrent.futures`...
- **get_anthropic_api_key** (f) `()` :25
- **ClaudeInvocationError** (C) :109
  - **__init__** (m) `(self, message: str, status_code: int = None, details: Any = None)` :111
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
)` :197
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
)` :327
- **invoke_parallel** (f) `(
    prompts: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
)` :402
- **invoke_parallel_streaming** (f) `(
    prompts: list[dict],
    callbacks: list[callable] = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
)` :531
- **InterruptToken** (C) :602
  - **__init__** (m) `(self)` :604
  - **interrupt** (m) `(self)` :607
  - **is_interrupted** (m) `(self)` :611
  - **reset** (m) `(self)` :615
- **invoke_parallel_interruptible** (f) `(
    prompts: list[dict],
    interrupt_token: InterruptToken = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
)` :620
- **ConversationThread** (C) :696
  - **__init__** (m) `(
        self,
        system: Union[str, list[dict], None] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        cache_system: bool = True
    )` :705
  - **send** (m) `(self, user_message: Union[str, list[dict]], cache_history: bool = True)` :730
  - **get_messages** (m) `(self)` :773
  - **clear** (m) `(self)` :777
  - **__len__** (m) `(self)` :781
- **get_available_models** (f) `()` :786
- **parse_json_response** (f) `(raw: str)` :803
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
)` :829

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

