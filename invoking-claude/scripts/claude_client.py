"""
Claude API Client Module

Provides functions for invoking Claude programmatically, including parallel invocations.
"""

import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

# Add api-credentials to path
api_credentials_path = Path(__file__).parent.parent.parent / "api-credentials" / "scripts"
sys.path.append(str(api_credentials_path))

try:
    from credentials import get_anthropic_api_key
except ImportError:
    raise ImportError(
        "Cannot import api-credentials skill. "
        "Ensure api-credentials skill is installed at: "
        f"{api_credentials_path.parent}"
    )

try:
    import anthropic
except ImportError:
    raise ImportError(
        "anthropic library not installed.\n"
        "Install with: pip install anthropic"
    )


class ClaudeInvocationError(Exception):
    """Custom exception for Claude API invocation errors"""
    def __init__(self, message: str, status_code: int = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def invoke_claude(
    prompt: str,
    model: str = "claude-sonnet-4-5-20250929",
    system: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    streaming: bool = False,
    **kwargs
) -> str:
    """
    Invoke Claude API with a single prompt.

    Args:
        prompt: The user message to send to Claude
        model: Claude model to use (default: claude-sonnet-4-5-20250929)
        system: Optional system prompt to set context/role
        max_tokens: Maximum tokens in response (default: 4096)
        temperature: Randomness 0-1 (default: 1.0)
        streaming: Enable streaming response (default: False)
        **kwargs: Additional API parameters (top_p, top_k, etc.)

    Returns:
        str: Response text from Claude

    Raises:
        ClaudeInvocationError: If API call fails
        ValueError: If parameters are invalid
    """
    if not prompt or not prompt.strip():
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
        "messages": [{"role": "user", "content": prompt}],
        **kwargs
    }

    if system:
        message_params["system"] = system

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


def invoke_parallel(
    prompts: list[dict],
    model: str = "claude-sonnet-4-5-20250929",
    max_tokens: int = 4096,
    max_workers: int = 5
) -> list[str]:
    """
    Invoke Claude API with multiple prompts in parallel.

    Uses ThreadPoolExecutor to run multiple API calls concurrently following
    the lightweight-workflow pattern.

    Args:
        prompts: List of dicts, each containing:
            - 'prompt' (required): The user message
            - 'system' (optional): System prompt
            - 'temperature' (optional): Temperature override
            - Other invoke_claude parameters
        model: Claude model for all invocations
        max_tokens: Max tokens per response
        max_workers: Max concurrent API calls (default: 5, max: 10)

    Returns:
        list[str]: List of responses in same order as prompts

    Raises:
        ValueError: If prompts is empty or invalid
        ClaudeInvocationError: If any API call fails
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
