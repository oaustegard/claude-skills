"""
Claude API Client Module

Provides functions for invoking Claude programmatically, including parallel invocations
and prompt caching support for optimized token usage.

See also:
- agent_pool.py: Named agents with inter-agent messaging and spawn reservation
- orchestration.py: Retry, reconciliation, and concurrency control
- task_state.py: Task lifecycle state machine
"""


# ---------------------------------------------------------------------------
# Execute Mode — default system prompt for autonomous sub-agents
# Adapted from OpenAI Codex collaboration-mode-templates/execute.md
# ---------------------------------------------------------------------------

EXECUTE_MODE = """You execute on a well-specified task independently and report results.

Execution rules:
- When information is missing, do NOT ask questions. Make a sensible assumption, state it briefly, and continue.
- Think out loud when it helps evaluate tradeoffs. Keep explanations short and grounded in consequences.
- Think ahead: what else might be needed? How will the result be validated?
- Be mindful of time. Minimize exploration; prefer direct action.
- If something fails, report what failed, what you tried, and what you will do next.
- When done, summarize what you delivered and how to validate it.

If other agents have sent you messages, incorporate their findings into your work.
Do not repeat their analysis — build on it."""

import json
import os
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Union
from copy import deepcopy

try:
    import anthropic
except ImportError:
    raise ImportError(
        "anthropic library not installed.\n"
        "Install with: uv pip install anthropic"
    )


# ---------------------------------------------------------------------------
# Blocked kwargs — defensive filter against params that silently break
# the response-reading assumptions of invoke_claude*. Inspired by Multica's
# per-vendor BlockedArgs pattern (server/pkg/agent/*.go).
#
# Passing these through **kwargs would land them in the SDK call and either
# change the response shape or duplicate a param the wrapper already owns.
# Rather than let that fail silently (or at a confusing distance from the
# caller), we strip them at the boundary and warn loudly.
# ---------------------------------------------------------------------------

_BLOCKED_KWARGS = {
    "stream": "use invoke_claude_streaming() or the streaming=True kwarg instead",
    "tools": "not supported — the wrapper reads content[0].text and assumes text",
    "tool_choice": "requires tools; not supported by the text-only response reader",
    "thinking": "extended thinking changes response shape; content[0] may be a thinking block",
}


def _filter_kwargs(kwargs: dict, fn_name: str) -> dict:
    """Strip kwargs that would break invoke_claude*'s assumptions. Warn on drop.

    Callers who genuinely need tools, thinking, or streaming should use the
    anthropic SDK directly — the wrappers here own a narrower contract.
    """
    import warnings
    safe = {}
    for k, v in kwargs.items():
        if k in _BLOCKED_KWARGS:
            warnings.warn(
                f"{fn_name}(): dropping kwarg {k!r} — {_BLOCKED_KWARGS[k]}",
                RuntimeWarning, stacklevel=3,
            )
            continue
        safe[k] = v
    return safe


def get_anthropic_api_key() -> str:
    """
    Get Anthropic API key from environment or project knowledge files.

    Priority order:
    1. ANTHROPIC_API_KEY environment variable
    2. API_KEY from /mnt/project/claude.env
    3. Individual file: /mnt/project/ANTHROPIC_API_KEY.txt
    4. Combined file: /mnt/project/API_CREDENTIALS.json

    Returns:
        str: Anthropic API key

    Raises:
        ValueError: If no API key found in any source
    """
    # Pattern 1: Environment variable (standard Anthropic convention)
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key

    # Pattern 2: claude.env file with API_KEY variable
    claude_env = Path("/mnt/project/claude.env")
    if claude_env.exists():
        try:
            for line in claude_env.read_text().splitlines():
                line = line.strip()
                if line.startswith("API_KEY="):
                    key = line[len("API_KEY="):].strip().strip('"').strip("'")
                    if key:
                        return key
        except (IOError, OSError) as e:
            raise ValueError(
                f"Found claude.env but couldn't read it: {e}\n"
                f"Please check file permissions"
            )

    # Pattern 3: Individual key file (recommended for project knowledge)
    key_file = Path("/mnt/project/ANTHROPIC_API_KEY.txt")
    if key_file.exists():
        try:
            key = key_file.read_text().strip()
            if key:
                return key
        except (IOError, OSError) as e:
            raise ValueError(
                f"Found ANTHROPIC_API_KEY.txt but couldn't read it: {e}\n"
                f"Please check file permissions or recreate the file"
            )

    # Pattern 4: Combined credentials file
    creds_file = Path("/mnt/project/API_CREDENTIALS.json")
    if creds_file.exists():
        try:
            with open(creds_file) as f:
                config = json.load(f)
                key = config.get("anthropic_api_key", "").strip()
                if key:
                    return key
        except (json.JSONDecodeError, IOError, OSError) as e:
            raise ValueError(
                f"Found API_CREDENTIALS.json but couldn't parse it: {e}\n"
                f"Please check file format"
            )

    # No key found - provide helpful error message
    raise ValueError(
        "No Anthropic API key found!\n\n"
        "Provide a key using one of these methods:\n\n"
        "Option 1 (recommended): Environment variable\n"
        "  export ANTHROPIC_API_KEY=sk-ant-api03-...\n\n"
        "Option 2: claude.env project knowledge file\n"
        "  File: claude.env\n"
        "  Content: API_KEY=sk-ant-api03-...\n\n"
        "Option 3: Individual file\n"
        "  File: ANTHROPIC_API_KEY.txt\n"
        "  Content: sk-ant-api03-...\n\n"
        "Option 4: Combined file\n"
        "  File: API_CREDENTIALS.json\n"
        "  Content: {\"anthropic_api_key\": \"sk-ant-api03-...\"}\n\n"
        "Get your API key from: https://console.anthropic.com/settings/keys"
    )


class ClaudeInvocationError(Exception):
    """Custom exception for Claude API invocation errors"""
    def __init__(self, message: str, status_code: int = None, details: Any = None, kind: str = "unknown"):
        super().__init__(message)
        self.status_code = status_code
        self.details = details
        self.kind = kind


# ---------------------------------------------------------------------------
# Error classification and recovery
# ---------------------------------------------------------------------------

# Error kinds returned in ClaudeInvocationError.kind
ERROR_RATE_LIMIT = "rate_limit"          # 429
ERROR_OVERLOADED = "overloaded"          # 529
ERROR_CONTEXT_TOO_LONG = "context_overflow"  # 400 + context length message
ERROR_OUTPUT_PARSE = "output_parse"      # JSON parse failure (invoke_claude_json)
ERROR_CONNECTION = "connection"          # Network errors
ERROR_AUTH = "auth"                      # 401/403
ERROR_UNKNOWN = "unknown"

_TRANSIENT_ERRORS = {ERROR_RATE_LIMIT, ERROR_OVERLOADED, ERROR_CONNECTION}


def _classify_error(error: Exception) -> str:
    """Classify an exception into an error kind."""
    if isinstance(error, anthropic.RateLimitError):
        return ERROR_RATE_LIMIT
    if isinstance(error, anthropic.APIStatusError):
        if error.status_code == 529:
            return ERROR_OVERLOADED
        if error.status_code in (401, 403):
            return ERROR_AUTH
        if error.status_code == 400:
            msg = str(error).lower()
            if "too long" in msg or "context" in msg or "token" in msg:
                return ERROR_CONTEXT_TOO_LONG
        return ERROR_UNKNOWN
    if isinstance(error, anthropic.APIConnectionError):
        return ERROR_CONNECTION
    if isinstance(error, json.JSONDecodeError):
        return ERROR_OUTPUT_PARSE
    return ERROR_UNKNOWN


def _backoff_delay(attempt: int, base: float = 1.0, cap: float = 30.0) -> float:
    """Exponential backoff with jitter, capped."""
    import random
    delay = min(base * (2 ** attempt), cap)
    return delay * (0.5 + random.random() * 0.5)


class Retry:
    """Return from on_error to retry with a modified prompt."""
    __slots__ = ("prompt", "system")
    def __init__(self, prompt=None, system=None):
        self.prompt = prompt    # replacement prompt (None = reuse original)
        self.system = system    # replacement system (None = reuse original)


class Fail:
    """Return from on_error to abort immediately."""
    __slots__ = ("message",)
    def __init__(self, message: str = ""):
        self.message = message


def _format_cache_control() -> dict:
    """Returns cache_control structure for ephemeral caching"""
    return {"type": "ephemeral"}


def _format_system_with_cache(
    system: Union[str, list[dict]],
    cache_system: bool = False
) -> Union[str, list[dict]]:
    """
    Format system prompt with optional cache_control.

    Args:
        system: System prompt (string or list of content blocks)
        cache_system: Whether to add cache_control to the last system block

    Returns:
        Formatted system prompt (string or list with cache_control)
    """
    if not system:
        return system

    if isinstance(system, str):
        if cache_system:
            # Convert string to content block with cache_control
            return [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": _format_cache_control()
                }
            ]
        return system

    # Already a list of content blocks
    if cache_system and len(system) > 0:
        # Add cache_control to last block if not present
        system = deepcopy(system)
        if "cache_control" not in system[-1]:
            system[-1]["cache_control"] = _format_cache_control()

    return system


def _format_message_with_cache(
    content: Union[str, list[dict]],
    cache_content: bool = False
) -> Union[str, list[dict]]:
    """
    Format message content with optional cache_control.

    Args:
        content: Message content (string or list of content blocks)
        cache_content: Whether to add cache_control to the last content block

    Returns:
        Formatted content (string or list with cache_control)
    """
    if isinstance(content, str):
        if cache_content:
            # Convert string to content block with cache_control
            return [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": _format_cache_control()
                }
            ]
        return content

    # Already a list of content blocks
    if cache_content and len(content) > 0:
        # Add cache_control to last block if not present
        content = deepcopy(content)
        if "cache_control" not in content[-1]:
            content[-1]["cache_control"] = _format_cache_control()

    return content


# @lat: [[orchestration#Claude API Client]]
def invoke_claude(
    prompt: Union[str, list[dict]],
    model: str = "claude-sonnet-4-6",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    streaming: bool = False,
    cache_system: bool = False,
    cache_prompt: bool = False,
    messages: list[dict] | None = None,
    max_retries: int = 0,
    on_error: callable = None,
    **kwargs
) -> str:
    """
    Invoke Claude API with a single prompt and optional error recovery.

    Args:
        prompt: The user message to send to Claude (string or list of content blocks)
        model: Claude model to use (default: claude-sonnet-4-6)
        system: Optional system prompt to set context/role (string or list of content blocks)
        max_tokens: Maximum tokens in response (default: 4096)
        temperature: Randomness 0-1 (default: 1.0)
        streaming: Enable streaming response (default: False)
        cache_system: Add cache_control to system prompt (requires 1024+ tokens, default: False)
        cache_prompt: Add cache_control to user prompt (requires 1024+ tokens, default: False)
        messages: Optional pre-built messages list (overrides prompt parameter)
        max_retries: Max retry attempts for transient errors (default: 0 = no retries).
            Transient errors (rate_limit, overloaded, connection) auto-retry with
            exponential backoff. Non-transient errors only retry if on_error returns Retry.
        on_error: Optional callback for custom recovery. Called as:
            on_error(error: ClaudeInvocationError, attempt: int) -> Retry | Fail | None
            - Return Retry(prompt=..., system=...) to retry with modified inputs
            - Return Fail(message=...) to abort immediately
            - Return None to use default behavior (retry transient, raise others)
        **kwargs: Additional API parameters (top_p, top_k, etc.)

    Returns:
        str: Response text from Claude

    Raises:
        ClaudeInvocationError: If API call fails after all retries
        ValueError: If parameters are invalid

    Note:
        Prompt caching requires minimum 1,024 tokens per cache breakpoint.
        Cache lifetime is 5 minutes, refreshed on each use.
        Maximum 4 cache breakpoints allowed per request.

    Examples:
        # Auto-retry transient errors (rate limits, overload, connection):
        response = invoke_claude("Analyze this", max_retries=3)

        # Custom recovery for context overflow:
        def handle_overflow(error, attempt):
            if error.kind == "context_overflow":
                return Retry(prompt="Summarize briefly: " + short_version)
            return None  # default behavior for other errors

        response = invoke_claude(long_prompt, max_retries=2, on_error=handle_overflow)
    """
    # Validate prompt unless using pre-built messages
    if not messages:
        if isinstance(prompt, str):
            if not prompt or not prompt.strip():
                raise ValueError("Prompt cannot be empty")
        elif not prompt:
            raise ValueError("Prompt cannot be empty")

    if max_tokens < 1 or max_tokens > 128000:
        raise ValueError("max_tokens must be between 1 and 128000")

    if not 0 <= temperature <= 1:
        raise ValueError("temperature must be between 0 and 1")

    try:
        api_key = get_anthropic_api_key()
    except ValueError as e:
        raise ClaudeInvocationError(
            f"Failed to get API key: {e}",
            status_code=None,
            details="Check api-credentials skill configuration",
            kind=ERROR_AUTH
        )

    client = anthropic.Anthropic(api_key=api_key)

    # Mutable state for retry loop
    current_prompt = prompt
    current_system = system
    last_error = None

    safe_kwargs = _filter_kwargs(kwargs, "invoke_claude")

    for attempt in range(max_retries + 1):
        # Build message parameters fresh each attempt (prompt/system may change)
        message_params = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **safe_kwargs
        }

        if messages:
            message_params["messages"] = messages
        else:
            content = _format_message_with_cache(current_prompt, cache_prompt)
            message_params["messages"] = [{"role": "user", "content": content}]

        if current_system:
            formatted_system = _format_system_with_cache(current_system, cache_system)
            message_params["system"] = formatted_system

        try:
            if streaming:
                full_response = ""
                with client.messages.stream(**message_params) as stream:
                    for text in stream.text_stream:
                        print(text, end="", flush=True)
                        full_response += text
                print()
                return full_response
            else:
                message = client.messages.create(**message_params)
                return message.content[0].text

        except (anthropic.APIStatusError, anthropic.APIConnectionError, Exception) as e:
            kind = _classify_error(e)
            status = getattr(e, 'status_code', None)
            msg = getattr(e, 'message', str(e))

            last_error = ClaudeInvocationError(
                f"API error (attempt {attempt + 1}/{max_retries + 1}): {msg}",
                status_code=status,
                details=getattr(e, 'response', type(e).__name__),
                kind=kind
            )

            # No retries left
            if attempt >= max_retries:
                break

            # Consult on_error callback if provided
            action = None
            if on_error:
                try:
                    action = on_error(last_error, attempt)
                except Exception:
                    break  # callback itself failed, give up

            if isinstance(action, Fail):
                raise ClaudeInvocationError(
                    action.message or str(last_error),
                    status_code=status,
                    details=last_error.details,
                    kind=kind
                )
            elif isinstance(action, Retry):
                # Caller wants to retry with modified inputs
                if action.prompt is not None:
                    current_prompt = action.prompt
                if action.system is not None:
                    current_system = action.system
                # Brief pause even for caller-directed retries
                time.sleep(_backoff_delay(attempt, base=0.5, cap=5.0))
                continue
            else:
                # Default: auto-retry transient errors, raise others
                if kind in _TRANSIENT_ERRORS:
                    delay = _backoff_delay(attempt)
                    time.sleep(delay)
                    continue
                else:
                    break  # non-transient, no custom recovery

    # All retries exhausted or non-retryable
    raise last_error


def _build_messages(
    prompt: Union[str, list[dict]],
    cache_prompt: bool = False
) -> list[dict]:
    """Build messages list from prompt with optional caching."""
    content = _format_message_with_cache(prompt, cache_prompt)
    return [{"role": "user", "content": content}]


def invoke_claude_streaming(
    prompt: Union[str, list[dict]],
    callback: callable = None,
    model: str = "claude-sonnet-4-6",
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

    # Format messages
    messages = _build_messages(prompt, cache_prompt)

    # Build stream params, conditionally including system
    stream_params = dict(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=messages,
        **_filter_kwargs(kwargs, "invoke_claude_streaming")
    )
    if system:
        stream_params["system"] = _format_system_with_cache(system, cache_system)

    accumulated_text = ""

    try:
        with client.messages.stream(**stream_params) as stream:
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


# @lat: [[orchestration#Parallel Execution]]
def invoke_parallel(
    prompts: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
    shared_system: Union[str, list[dict], None] = None,
    cache_shared_system: bool = False
) -> list[str]:
    """
    Invoke Claude API with multiple prompts in parallel.

    Uses ThreadPoolExecutor to run multiple API calls concurrently following
    the lightweight-workflow pattern.

    Args:
        prompts: List of dicts, each containing:
            - 'prompt' (required): The user message
            - 'system' (optional): System prompt (appended to shared_system if both provided)
            - 'temperature' (optional): Temperature override
            - 'cache_system' (optional): Cache individual system prompt
            - 'cache_prompt' (optional): Cache individual user prompt
            - Other invoke_claude parameters
        model: Claude model for all invocations
        max_tokens: Max tokens per response
        max_workers: Max concurrent API calls (default: 5, max: 10)
        shared_system: System context shared across ALL invocations (for cache efficiency)
        cache_shared_system: Add cache_control to shared_system (default: False)

    Returns:
        list[str]: List of responses in same order as prompts

    Raises:
        ValueError: If prompts is empty or invalid
        ClaudeInvocationError: If any API call fails

    Note:
        For optimal caching: provide large common context in shared_system with
        cache_shared_system=True. First invocation creates cache, subsequent ones
        reuse it (90% cost reduction for cached content).
    """
    if not prompts:
        raise ValueError("prompts list cannot be empty")

    if not isinstance(prompts, list):
        raise ValueError("prompts must be a list of dicts")

    for i, prompt_dict in enumerate(prompts):
        if not isinstance(prompt_dict, dict):
            raise ValueError(f"prompts[{i}] must be a dict, got {type(prompt_dict)}")
        if 'prompt' not in prompt_dict:
            raise ValueError(f"prompts[{i}] missing required 'prompt' key")

    # Clamp max_workers
    max_workers = max(1, min(max_workers, 10))

    # Format shared system context with caching if provided
    formatted_shared_system = None
    if shared_system:
        formatted_shared_system = _format_system_with_cache(
            shared_system,
            cache_shared_system
        )

    # Storage for results with indices to maintain order
    results = [None] * len(prompts)
    errors = []

    def invoke_with_index(index: int, prompt_dict: dict) -> tuple[int, str]:
        """Wrapper to track original index"""
        try:
            # Extract parameters
            prompt = prompt_dict['prompt']
            params = {k: v for k, v in prompt_dict.items() if k != 'prompt'}
            params['model'] = params.get('model', model)
            params['max_tokens'] = params.get('max_tokens', max_tokens)

            # Merge shared_system with individual system prompt if both exist
            if formatted_shared_system:
                individual_system = params.get('system')
                if individual_system:
                    # Combine shared and individual system prompts
                    # shared_system is cached, individual_system follows
                    if isinstance(formatted_shared_system, str):
                        shared_blocks = [{"type": "text", "text": formatted_shared_system}]
                    else:
                        shared_blocks = formatted_shared_system

                    if isinstance(individual_system, str):
                        individual_blocks = [{"type": "text", "text": individual_system}]
                    else:
                        individual_blocks = individual_system

                    params['system'] = shared_blocks + individual_blocks
                else:
                    params['system'] = formatted_shared_system

            response = invoke_claude(prompt, **params)
            return index, response
        except Exception as e:
            return index, e

    # Execute in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(invoke_with_index, i, prompt_dict): i
            for i, prompt_dict in enumerate(prompts)
        }

        # Collect results as they complete
        for future in as_completed(futures):
            index, result = future.result()
            if isinstance(result, Exception):
                errors.append((index, result))
            else:
                results[index] = result

    # If any errors occurred, raise the first one
    if errors:
        index, error = errors[0]
        raise ClaudeInvocationError(
            f"Invocation {index} failed: {error}",
            status_code=getattr(error, 'status_code', None),
            details=f"{len(errors)} of {len(prompts)} invocations failed"
        )

    return results


def invoke_parallel_streaming(
    prompts: list[dict],
    callbacks: list[callable] = None,
    model: str = "claude-sonnet-4-6",
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


# @lat: [[orchestration#Stall Detection]]
class StallDetector:
    """
    Detects stalled operations by tracking activity timestamps.

    Monitors the time since last activity and triggers timeout/retry
    when an operation becomes unresponsive.

    Args:
        timeout: Seconds of inactivity before considering a task stalled (default: 60)
        on_stall: Optional callback invoked when stall is detected.
            Receives (task_id: str, idle_seconds: float).
    """

    def __init__(self, timeout: float = 60.0, on_stall: callable = None):
        self._lock = threading.Lock()
        self.timeout = timeout
        self.on_stall = on_stall
        self._timestamps: dict[str, float] = {}
        self._stopped = threading.Event()
        self._monitor_thread: threading.Thread | None = None

    def register(self, task_id: str) -> None:
        """Start tracking a task."""
        with self._lock:
            self._timestamps[task_id] = time.monotonic()

    def heartbeat(self, task_id: str) -> None:
        """Record activity for a task (resets its stall timer)."""
        with self._lock:
            if task_id in self._timestamps:
                self._timestamps[task_id] = time.monotonic()

    def unregister(self, task_id: str) -> None:
        """Stop tracking a task."""
        with self._lock:
            self._timestamps.pop(task_id, None)

    def check_stalled(self) -> list[tuple[str, float]]:
        """
        Check for stalled tasks.

        Returns:
            List of (task_id, idle_seconds) for tasks exceeding timeout.
        """
        now = time.monotonic()
        stalled = []
        with self._lock:
            for task_id, last_active in self._timestamps.items():
                idle = now - last_active
                if idle >= self.timeout:
                    stalled.append((task_id, idle))
        return stalled

    def start_monitoring(self, poll_interval: float = 5.0) -> None:
        """
        Start a background thread that periodically checks for stalls.

        Args:
            poll_interval: Seconds between checks (default: 5.0)
        """
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stopped.clear()

        def _monitor():
            while not self._stopped.wait(poll_interval):
                stalled = self.check_stalled()
                if stalled and self.on_stall:
                    for task_id, idle_secs in stalled:
                        self.on_stall(task_id, idle_secs)

        self._monitor_thread = threading.Thread(
            target=_monitor, daemon=True, name="stall-detector"
        )
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread."""
        self._stopped.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None


# @lat: [[orchestration#Parallel Execution]]
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
    model: str = "claude-sonnet-4-6",
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


# @lat: [[orchestration#Conversation Threads]]
class ConversationThread:
    """
    Manages multi-turn conversations with automatic prompt caching.

    Automatically caches conversation history to reduce token costs in
    subsequent turns. Ideal for orchestrator -> sub-agent patterns where
    each sub-agent maintains its own conversation state.

    Supports continuation turn semantics: the first turn receives the full
    prompt, while subsequent turns receive lightweight continuation guidance.
    """

    def __init__(
        self,
        system: Union[str, list[dict], None] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        cache_system: bool = True,
        max_turns: int | None = None,
        continuation_prompt: str | None = None
    ):
        """
        Initialize a new conversation thread.

        Args:
            system: System prompt for this conversation
            model: Claude model to use
            max_tokens: Maximum tokens per response
            temperature: Temperature setting
            cache_system: Cache the system prompt (default: True)
            max_turns: Optional maximum number of turns before stopping (None = unlimited)
            continuation_prompt: Default prompt for send_continuation() calls.
                Defaults to "Continue from where you left off."
        """
        self.system = system
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.cache_system = cache_system
        self.max_turns = max_turns
        self.continuation_prompt = (
            continuation_prompt or "Continue from where you left off."
        )
        self.messages: list[dict] = []

    def send(self, user_message: Union[str, list[dict]], cache_history: bool = True) -> str:
        """
        Send a message and get a response.

        Args:
            user_message: The user message to send
            cache_history: Cache conversation history up to this point (default: True)

        Returns:
            str: Claude's response

        Note:
            When cache_history=True, the entire conversation history up to and
            including this user message will be cached for the next turn.
        """
        # Enforce max_turns
        if self.max_turns is not None and self.turn_count >= self.max_turns:
            raise RuntimeError(
                f"Maximum turns ({self.max_turns}) reached"
            )

        # Format user message content
        content = _format_message_with_cache(user_message, cache_history)
        self.messages.append({"role": "user", "content": content})

        # Make API call with full conversation history
        response = invoke_claude(
            prompt="",  # Not used when messages provided
            model=self.model,
            system=self.system,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            cache_system=self.cache_system,
            messages=self.messages
        )

        # Add assistant response to history (no caching on assistant messages)
        self.messages.append({"role": "assistant", "content": response})

        # Remove cache_control from previous messages since we're caching the latest
        if cache_history and len(self.messages) >= 3:
            # Remove cache_control from older user messages
            for msg in self.messages[:-2]:
                if msg["role"] == "user" and isinstance(msg["content"], list):
                    for block in msg["content"]:
                        block.pop("cache_control", None)

        return response

    @property
    def turn_count(self) -> int:
        """Number of completed user/assistant turn pairs."""
        return len(self.messages) // 2

    def send_continuation(
        self,
        guidance: str | None = None,
        cache_history: bool = True
    ) -> str:
        """
        Send a lightweight continuation turn.

        Uses reduced guidance instead of a full prompt, following the
        continuation turn protocol: first turn gets the full prompt,
        subsequent turns get only continuation guidance.

        Args:
            guidance: Optional continuation guidance. Defaults to
                self.continuation_prompt if not provided.
            cache_history: Cache conversation history (default: True)

        Returns:
            str: Claude's response

        Raises:
            RuntimeError: If no previous turns exist (use send() first)
            RuntimeError: If max_turns has been reached
        """
        if not self.messages:
            raise RuntimeError(
                "No previous turns. Use send() for the first turn."
            )
        if self.max_turns is not None and self.turn_count >= self.max_turns:
            raise RuntimeError(
                f"Maximum turns ({self.max_turns}) reached"
            )
        prompt = guidance or self.continuation_prompt
        return self.send(prompt, cache_history=cache_history)

    def get_messages(self) -> list[dict]:
        """Get the current conversation history"""
        return deepcopy(self.messages)

    def clear(self):
        """Clear conversation history"""
        self.messages = []

    def __len__(self) -> int:
        """Return number of turns (user + assistant pairs)"""
        return len(self.messages) // 2


def get_available_models() -> list[str]:
    """
    Returns list of available Claude models.

    Returns:
        list[str]: List of model identifiers
    """
    return [
        "claude-sonnet-4-6",               # Latest Sonnet (default)
        "claude-opus-4-6",                  # Latest Opus (highest capability)
        "claude-haiku-4-5-20251001",        # Haiku 4.5 (fast, cost-effective)
        "claude-sonnet-4-5-20250929",       # Legacy Sonnet 4.5
        "claude-sonnet-4-20250514",         # Legacy Sonnet 4
        "claude-opus-4-20250514",           # Legacy Opus 4
    ]


def parse_json_response(raw: str) -> dict:
    """
    Parse a JSON response from Claude, stripping markdown code fences if present.

    Claude sometimes wraps JSON in markdown fences (```json ... ```) despite
    instructions to return plain JSON. This utility handles both cases.

    Args:
        raw: Raw response text from Claude (with or without markdown fences)

    Returns:
        dict: Parsed JSON object

    Raises:
        json.JSONDecodeError: If the text cannot be parsed as JSON after stripping fences
    """
    text = raw.strip()
    if text.startswith("```"):
        # Strip opening fence (```json or ``` or any variant)
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        # Strip closing fence
        text = text.rsplit("```", 1)[0]
        text = text.strip()
    return json.loads(text)


def invoke_claude_json(
    prompt: Union[str, list[dict]],
    model: str = "claude-sonnet-4-6",
    system: Union[str, list[dict], None] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    cache_system: bool = False,
    cache_prompt: bool = False,
    messages: list[dict] | None = None,
    max_parse_retries: int = 1,
    **kwargs
) -> dict:
    """
    Invoke Claude and parse the response as JSON, with automatic retry on parse failure.

    On JSON parse failure, automatically retries by sending the malformed output back
    to Claude with a repair prompt. This handles the common case where Claude wraps
    JSON in prose or produces slightly malformed output.

    Args:
        prompt: The user message to send to Claude
        model: Claude model to use
        system: Optional system prompt
        max_tokens: Maximum tokens in response
        temperature: Randomness 0-1
        cache_system: Add cache_control to system prompt
        cache_prompt: Add cache_control to user prompt
        messages: Optional pre-built messages list
        max_parse_retries: Max retries on JSON parse failure (default: 1).
            Set to 0 to disable parse recovery (old behavior).
        **kwargs: Additional API parameters

    Returns:
        dict: Parsed JSON response

    Raises:
        ClaudeInvocationError: If API call fails
        json.JSONDecodeError: If response cannot be parsed as JSON after retries
    """
    # Pass through max_retries/on_error if caller provided them
    raw = invoke_claude(
        prompt=prompt,
        model=model,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
        cache_system=cache_system,
        cache_prompt=cache_prompt,
        messages=messages,
        **kwargs
    )

    # Try parsing
    try:
        return parse_json_response(raw)
    except json.JSONDecodeError as first_error:
        if max_parse_retries < 1:
            raise

    # Parse failed — retry with repair prompt
    for repair_attempt in range(max_parse_retries):
        repair_prompt = (
            "Your previous response could not be parsed as JSON. "
            "Here is what you returned:\n\n"
            f"```\n{raw[:2000]}\n```\n\n"
            "Please respond with ONLY valid JSON, no markdown fences, "
            "no prose before or after. Just the JSON object."
        )
        try:
            raw = invoke_claude(
                prompt=repair_prompt,
                model=model,
                system=system,
                max_tokens=max_tokens,
                temperature=max(0.0, temperature - 0.3),  # lower temp for repair
                cache_system=cache_system,
                **kwargs
            )
            return parse_json_response(raw)
        except json.JSONDecodeError:
            if repair_attempt >= max_parse_retries - 1:
                raise
            continue


if __name__ == "__main__":
    # Simple test
    print("Testing Claude API invocation...")

    try:
        # Test 1: Simple invocation
        print("\n=== Test 1: Simple Invocation ===")
        response = invoke_claude(
            "Say hello in exactly 5 words.",
            max_tokens=50
        )
        print(f"Response: {response}")

        # Test 2: Parallel invocations
        print("\n=== Test 2: Parallel Invocations ===")
        prompts = [
            {"prompt": "What is 2+2? Answer in one number."},
            {"prompt": "What is 3+3? Answer in one number."},
            {"prompt": "What is 5+5? Answer in one number."}
        ]
        responses = invoke_parallel(prompts, max_tokens=20)
        for i, resp in enumerate(responses):
            print(f"Response {i+1}: {resp}")

        print("\n✓ All tests passed!")

    except ClaudeInvocationError as e:
        print(f"\n✗ Invocation error: {e}")
        if e.status_code:
            print(f"  Status code: {e.status_code}")
        if e.details:
            print(f"  Details: {e.details}")
        exit(1)
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        exit(1)
