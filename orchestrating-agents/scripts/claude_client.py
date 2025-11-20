"""
Claude API Client Module

Provides functions for invoking Claude programmatically, including parallel invocations
and prompt caching support for optimized token usage.
"""

import json
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


def get_anthropic_api_key() -> str:
    """
    Get Anthropic API key from project knowledge files.

    Priority order:
    1. Individual file: /mnt/project/ANTHROPIC_API_KEY.txt
    2. Combined file: /mnt/project/API_CREDENTIALS.json

    Returns:
        str: Anthropic API key

    Raises:
        ValueError: If no API key found in any source
    """
    # Pattern 1: Individual key file (recommended)
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

    # Pattern 2: Combined credentials file
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
        "Add a project knowledge file using one of these methods:\n\n"
        "Option 1 (recommended): Individual file\n"
        "  File: ANTHROPIC_API_KEY.txt\n"
        "  Content: sk-ant-api03-...\n\n"
        "Option 2: Combined file\n"
        "  File: API_CREDENTIALS.json\n"
        "  Content: {\"anthropic_api_key\": \"sk-ant-api03-...\"}\n\n"
        "Get your API key from: https://console.anthropic.com/settings/keys"
    )


class ClaudeInvocationError(Exception):
    """Custom exception for Claude API invocation errors"""
    def __init__(self, message: str, status_code: int = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


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


def invoke_claude(
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
) -> str:
    """
    Invoke Claude API with a single prompt.

    Args:
        prompt: The user message to send to Claude (string or list of content blocks)
        model: Claude model to use (default: claude-sonnet-4-5-20250929)
        system: Optional system prompt to set context/role (string or list of content blocks)
        max_tokens: Maximum tokens in response (default: 4096)
        temperature: Randomness 0-1 (default: 1.0)
        streaming: Enable streaming response (default: False)
        cache_system: Add cache_control to system prompt (requires 1024+ tokens, default: False)
        cache_prompt: Add cache_control to user prompt (requires 1024+ tokens, default: False)
        messages: Optional pre-built messages list (overrides prompt parameter)
        **kwargs: Additional API parameters (top_p, top_k, etc.)

    Returns:
        str: Response text from Claude

    Raises:
        ClaudeInvocationError: If API call fails
        ValueError: If parameters are invalid

    Note:
        Prompt caching requires minimum 1,024 tokens per cache breakpoint.
        Cache lifetime is 5 minutes, refreshed on each use.
        Maximum 4 cache breakpoints allowed per request.
    """
    # Validate prompt unless using pre-built messages
    if not messages:
        if isinstance(prompt, str):
            if not prompt or not prompt.strip():
                raise ValueError("Prompt cannot be empty")
        elif not prompt:
            raise ValueError("Prompt cannot be empty")

    if max_tokens < 1 or max_tokens > 8192:
        raise ValueError("max_tokens must be between 1 and 8192")

    if not 0 <= temperature <= 1:
        raise ValueError("temperature must be between 0 and 1")

    try:
        api_key = get_anthropic_api_key()
    except ValueError as e:
        raise ClaudeInvocationError(
            f"Failed to get API key: {e}",
            status_code=None,
            details="Check api-credentials skill configuration"
        )

    client = anthropic.Anthropic(api_key=api_key)

    # Build message parameters
    message_params = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        **kwargs
    }

    # Handle messages (pre-built or from prompt)
    if messages:
        # Use pre-built messages list (for multi-turn conversations)
        message_params["messages"] = messages
    else:
        # Build single message from prompt with optional caching
        content = _format_message_with_cache(prompt, cache_prompt)
        message_params["messages"] = [{"role": "user", "content": content}]

    # Handle system prompt with optional caching
    if system:
        formatted_system = _format_system_with_cache(system, cache_system)
        message_params["system"] = formatted_system

    try:
        if streaming:
            # Streaming mode
            full_response = ""
            with client.messages.stream(**message_params) as stream:
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                    full_response += text
            print()  # Newline after stream
            return full_response
        else:
            # Non-streaming mode
            message = client.messages.create(**message_params)
            return message.content[0].text

    except anthropic.APIStatusError as e:
        raise ClaudeInvocationError(
            f"API request failed: {e.message}",
            status_code=e.status_code,
            details=e.response
        )
    except anthropic.APIConnectionError as e:
        raise ClaudeInvocationError(
            f"Connection error: {e}",
            status_code=None,
            details="Check network connection"
        )
    except Exception as e:
        raise ClaudeInvocationError(
            f"Unexpected error: {e}",
            status_code=None,
            details=type(e).__name__
        )


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


def invoke_parallel(
    prompts: list[dict],
    model: str = "claude-sonnet-4-5-20250929",
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


class ConversationThread:
    """
    Manages multi-turn conversations with automatic prompt caching.

    Automatically caches conversation history to reduce token costs in
    subsequent turns. Ideal for orchestrator -> sub-agent patterns where
    each sub-agent maintains its own conversation state.
    """

    def __init__(
        self,
        system: Union[str, list[dict], None] = None,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        cache_system: bool = True
    ):
        """
        Initialize a new conversation thread.

        Args:
            system: System prompt for this conversation
            model: Claude model to use
            max_tokens: Maximum tokens per response
            temperature: Temperature setting
            cache_system: Cache the system prompt (default: True)
        """
        self.system = system
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.cache_system = cache_system
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
        "claude-sonnet-4-5-20250929",
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
    ]


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
