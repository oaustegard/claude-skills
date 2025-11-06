#!/usr/bin/env python3
"""
Gemini API Client

Provides high-level functions for invoking Google Gemini models
with support for structured outputs, parallel processing, and error handling.
"""

import sys
import time
from typing import Optional, Any, Type, Union
from pathlib import Path
import json

# Import credentials module
sys.path.append('/mnt/skills/api-credentials/scripts')
from credentials import get_google_api_key

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerateContentResponse
    from pydantic import BaseModel
except ImportError as e:
    print(f"Error: Required package not installed: {e}")
    print("Install with: pip install google-generativeai pydantic --break-system-packages")
    sys.exit(1)


# Available models
MODELS = {
    "gemini-2.0-flash-exp": "gemini-2.0-flash-exp",
    "gemini-1.5-pro": "gemini-1.5-pro",
    "gemini-1.5-flash": "gemini-1.5-flash",
}

DEFAULT_MODEL = "gemini-2.0-flash-exp"


def _initialize_client() -> bool:
    """
    Initialize the Gemini API client with credentials.

    Returns:
        True if initialization successful, False otherwise
    """
    api_key = get_google_api_key()
    if not api_key:
        print("Error: Google API key not configured")
        print("Create /home/claude/config.json with 'google_api_key' field")
        print("See api-credentials skill for details")
        return False

    genai.configure(api_key=api_key)
    return True


def invoke_gemini(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    image_path: Optional[str] = None,
) -> Optional[str]:
    """
    Invoke Gemini model with a text prompt.

    Args:
        prompt: The text prompt to send
        model: Model name (default: gemini-2.0-flash-exp)
        temperature: Sampling temperature (0.0-1.0)
        max_output_tokens: Maximum tokens in response
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        image_path: Optional path to image file for multi-modal input

    Returns:
        Response text if successful, None if error
    """
    if not _initialize_client():
        return None

    if model not in MODELS:
        raise ValueError(f"Invalid model: {model}. Choose from {list(MODELS.keys())}")

    try:
        # Build generation config
        generation_config = {
            "temperature": temperature,
        }
        if max_output_tokens:
            generation_config["max_output_tokens"] = max_output_tokens
        if top_p is not None:
            generation_config["top_p"] = top_p
        if top_k is not None:
            generation_config["top_k"] = top_k

        # Initialize model
        model_instance = genai.GenerativeModel(
            model_name=MODELS[model],
            generation_config=generation_config
        )

        # Prepare content
        if image_path:
            # Multi-modal input
            from PIL import Image
            image = Image.open(image_path)
            content = [prompt, image]
        else:
            content = prompt

        # Generate response with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model_instance.generate_content(content)
                return response.text
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Retry {attempt + 1}/{max_retries} after {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

    except Exception as e:
        print(f"Error invoking Gemini: {e}")
        return None


def invoke_with_structured_output(
    prompt: str,
    pydantic_model: Type[BaseModel],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    image_path: Optional[str] = None,
) -> Optional[BaseModel]:
    """
    Invoke Gemini with structured output using Pydantic model.

    Args:
        prompt: The text prompt to send
        pydantic_model: Pydantic model class for response schema
        model: Model name (default: gemini-2.0-flash-exp)
        temperature: Sampling temperature (0.0-1.0)
        image_path: Optional path to image file for multi-modal input

    Returns:
        Instance of pydantic_model if successful, None if error
    """
    if not _initialize_client():
        return None

    if model not in MODELS:
        raise ValueError(f"Invalid model: {model}. Choose from {list(MODELS.keys())}")

    try:
        # Initialize model with response schema
        model_instance = genai.GenerativeModel(
            model_name=MODELS[model],
            generation_config={
                "temperature": temperature,
                "response_mime_type": "application/json",
                "response_schema": pydantic_model,
            }
        )

        # Prepare content
        if image_path:
            from PIL import Image
            image = Image.open(image_path)
            content = [prompt, image]
        else:
            content = prompt

        # Generate response with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model_instance.generate_content(content)
                # Parse JSON response into Pydantic model
                json_data = json.loads(response.text)
                return pydantic_model(**json_data)
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Retry {attempt + 1}/{max_retries} after {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

    except Exception as e:
        print(f"Error invoking Gemini with structured output: {e}")
        return None


def invoke_parallel(
    prompts: list[str],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_workers: int = 5,
) -> list[Optional[str]]:
    """
    Invoke Gemini with multiple prompts in parallel.

    Args:
        prompts: List of text prompts to process
        model: Model name (default: gemini-2.0-flash-exp)
        temperature: Sampling temperature (0.0-1.0)
        max_workers: Maximum concurrent requests

    Returns:
        List of responses in same order as prompts
    """
    if not _initialize_client():
        return [None] * len(prompts)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = [None] * len(prompts)

    def process_prompt(idx: int, prompt: str) -> tuple[int, Optional[str]]:
        """Process a single prompt and return index with result"""
        response = invoke_gemini(prompt, model=model, temperature=temperature)
        return idx, response

    # Process prompts in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_prompt, idx, prompt): idx
            for idx, prompt in enumerate(prompts)
        }

        for future in as_completed(futures):
            try:
                idx, response = future.result()
                results[idx] = response
            except Exception as e:
                idx = futures[future]
                print(f"Error processing prompt {idx}: {e}")
                results[idx] = None

    return results


def get_available_models() -> list[str]:
    """
    Get list of available Gemini models.

    Returns:
        List of model names
    """
    return list(MODELS.keys())


def verify_setup() -> bool:
    """
    Verify that Gemini client is properly configured.

    Returns:
        True if setup is valid, False otherwise
    """
    if not _initialize_client():
        return False

    # Test with minimal prompt
    try:
        test_response = invoke_gemini("Say 'OK'", model=DEFAULT_MODEL)
        return test_response is not None
    except Exception as e:
        print(f"Setup verification failed: {e}")
        return False


if __name__ == "__main__":
    # Self-test
    print("Gemini Client Self-Test")
    print("=" * 50)

    print("\n1. Checking setup...")
    if verify_setup():
        print("   ✓ Setup verified")
    else:
        print("   ✗ Setup failed")
        sys.exit(1)

    print("\n2. Available models:")
    for model_name in get_available_models():
        print(f"   - {model_name}")

    print("\n3. Testing basic invocation...")
    response = invoke_gemini("What is 2+2? Answer in one word.", model=DEFAULT_MODEL)
    if response:
        print(f"   Response: {response.strip()}")
    else:
        print("   ✗ Invocation failed")

    print("\n4. Testing structured output...")
    from pydantic import BaseModel, Field

    class MathAnswer(BaseModel):
        result: int = Field(description="The numerical result")
        explanation: str = Field(description="Brief explanation")

    structured = invoke_with_structured_output(
        prompt="What is 5+7? Provide result and explanation.",
        pydantic_model=MathAnswer,
        model=DEFAULT_MODEL
    )

    if structured:
        print(f"   Result: {structured.result}")
        print(f"   Explanation: {structured.explanation}")
    else:
        print("   ✗ Structured output failed")

    print("\n5. Testing parallel invocation...")
    test_prompts = [
        "What is the capital of France? One word.",
        "What is the capital of Japan? One word.",
        "What is the capital of Brazil? One word.",
    ]
    parallel_results = invoke_parallel(test_prompts, model=DEFAULT_MODEL)
    for prompt, result in zip(test_prompts, parallel_results):
        if result:
            print(f"   {prompt[:30]}... → {result.strip()}")
        else:
            print(f"   {prompt[:30]}... → Failed")

    print("\n" + "=" * 50)
    print("Self-test complete!")
