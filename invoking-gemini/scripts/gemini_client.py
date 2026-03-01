#!/usr/bin/env python3
"""
Gemini API Client

Routes requests through Cloudflare AI Gateway when configured (preferred)
or directly to Google's Generative Language API via the google-generativeai
SDK (fallback).

Credential priority:
1. CF Gateway: proxy.env with CF_ACCOUNT_ID, CF_GATEWAY_ID, CF_API_TOKEN
2. Direct API:  GOOGLE_API_KEY.txt or API_CREDENTIALS.json
"""

import json
import os
import time
from pathlib import Path
from typing import Optional, Type

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from pydantic import BaseModel
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    BaseModel = object  # type: ignore[assignment,misc]

if not HAS_REQUESTS and not HAS_GENAI:
    print("Error: neither 'requests' nor 'google-generativeai' is installed.")
    print("Install with: uv pip install requests google-generativeai pydantic")
    import sys
    sys.exit(1)


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

MODELS = {
    "gemini-2.0-flash-exp": "gemini-2.0-flash-exp",
    "gemini-2.0-flash": "gemini-2.0-flash",
    "gemini-1.5-pro": "gemini-1.5-pro",
    "gemini-1.5-flash": "gemini-1.5-flash",
}

DEFAULT_MODEL = "gemini-2.0-flash-exp"

# ---------------------------------------------------------------------------
# Cloudflare AI Gateway constants
# ---------------------------------------------------------------------------

_CF_GATEWAY_BASE = "https://gateway.ai.cloudflare.com/v1"

_PROXY_ENV_PATHS = [
    Path("/mnt/project/proxy.env"),
    Path("/mnt/user-data/proxy.env"),
    Path.home() / ".muninn" / "proxy.env",
]


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def _parse_env_file(path: Path) -> dict:
    """Parse a .env-format file into a dict, stripping quotes."""
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def get_cf_credentials() -> Optional[dict]:
    """
    Load Cloudflare AI Gateway credentials.

    Searches for proxy.env in well-known paths, then falls back to
    environment variables.

    Required keys: CF_ACCOUNT_ID, CF_GATEWAY_ID, CF_API_TOKEN
    Optional key:  GOOGLE_API_KEY (for non-BYOK setups)

    Returns:
        dict with credentials if fully configured, None otherwise
    """
    required = ("CF_ACCOUNT_ID", "CF_GATEWAY_ID", "CF_API_TOKEN")

    for env_path in _PROXY_ENV_PATHS:
        if env_path.exists():
            try:
                creds = _parse_env_file(env_path)
                if all(creds.get(k) for k in required):
                    return creds
            except (IOError, OSError):
                continue

    # Fall back to environment variables
    creds = {k: os.environ.get(k, "") for k in required}
    creds["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "")
    if all(creds.get(k) for k in required):
        return creds

    return None


def get_google_api_key() -> str:
    """
    Get Google API key for direct (non-gateway) access.

    Priority order:
    1. Individual file: /mnt/project/GOOGLE_API_KEY.txt
    2. Combined file:   /mnt/project/API_CREDENTIALS.json
    3. Environment variable: GOOGLE_API_KEY

    Returns:
        str: Google API key

    Raises:
        ValueError: If no API key found in any source
    """
    # 1. Individual key file
    key_file = Path("/mnt/project/GOOGLE_API_KEY.txt")
    if key_file.exists():
        try:
            key = key_file.read_text().strip()
            if key:
                return key
        except (IOError, OSError) as e:
            raise ValueError(f"Found GOOGLE_API_KEY.txt but couldn't read it: {e}")

    # 2. Combined credentials file
    creds_file = Path("/mnt/project/API_CREDENTIALS.json")
    if creds_file.exists():
        try:
            with open(creds_file) as f:
                config = json.load(f)
            key = config.get("google_api_key", "").strip()
            if key:
                return key
        except (json.JSONDecodeError, IOError, OSError) as e:
            raise ValueError(f"Found API_CREDENTIALS.json but couldn't parse it: {e}")

    # 3. Environment variable
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if key:
        return key

    raise ValueError(
        "No Google API key found!\n\n"
        "Option A (recommended): Configure Cloudflare AI Gateway\n"
        "  File: /mnt/project/proxy.env\n"
        "  Content:\n"
        "    CF_ACCOUNT_ID=<your-account-id>\n"
        "    CF_GATEWAY_ID=<your-gateway-id>\n"
        "    CF_API_TOKEN=<your-cf-api-token>\n\n"
        "Option B: Direct Google API\n"
        "  File: GOOGLE_API_KEY.txt  (content: AIzaSy...)\n"
        "  or\n"
        "  File: API_CREDENTIALS.json  (content: {\"google_api_key\": \"AIzaSy...\"})\n\n"
        "Get your Cloudflare token: https://dash.cloudflare.com/profile/api-tokens\n"
        "Get your Google key: https://console.cloud.google.com/apis/credentials"
    )


# ---------------------------------------------------------------------------
# Cloudflare AI Gateway — REST path
# ---------------------------------------------------------------------------

def _cf_request(
    model_id: str,
    contents: list,
    generation_config: dict,
    cf_creds: dict,
) -> dict:
    """
    POST a generateContent request via Cloudflare AI Gateway.

    Args:
        model_id: Gemini model ID (e.g., 'gemini-2.0-flash-exp')
        contents: Gemini REST API contents array
        generation_config: generationConfig dict (camelCase keys)
        cf_creds: dict with CF_ACCOUNT_ID, CF_GATEWAY_ID, CF_API_TOKEN

    Returns:
        Parsed JSON response dict

    Raises:
        requests.HTTPError: On non-2xx HTTP response
    """
    account_id = cf_creds["CF_ACCOUNT_ID"]
    gateway_id = cf_creds["CF_GATEWAY_ID"]
    api_token = cf_creds["CF_API_TOKEN"]

    url = (
        f"{_CF_GATEWAY_BASE}/{account_id}/{gateway_id}"
        f"/google-ai-studio/v1beta/models/{model_id}:generateContent"
    )

    # Include Google API key as query param for non-BYOK setups
    google_key = cf_creds.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    if google_key:
        url += f"?key={google_key}"

    payload: dict = {"contents": contents}
    if generation_config:
        payload["generationConfig"] = generation_config

    headers = {
        "Content-Type": "application/json",
        "cf-aig-authorization": f"Bearer {api_token}",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=120)
    response.raise_for_status()
    return response.json()


def _extract_text(response: dict) -> Optional[str]:
    """Extract generated text from a Gemini REST API response."""
    try:
        return response["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return None


def _build_contents(prompt: str, image_path: Optional[str]) -> list:
    """Build the Gemini REST API 'contents' array."""
    parts: list = [{"text": prompt}]
    if image_path:
        import base64
        import mimetypes

        image_data = Path(image_path).read_bytes()
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(image_data).decode(),
            }
        })
    return [{"parts": parts}]


def _pydantic_to_schema(model_class: Type) -> dict:
    """Convert a Pydantic model class to a Gemini-compatible JSON schema dict."""
    try:
        schema = model_class.model_json_schema()  # Pydantic v2
    except AttributeError:
        schema = model_class.schema()  # Pydantic v1

    # Strip metadata keys that Gemini rejects
    for key in ("$schema", "title"):
        schema.pop(key, None)

    return schema


# ---------------------------------------------------------------------------
# Direct SDK path helpers
# ---------------------------------------------------------------------------

def _initialize_direct_client() -> bool:
    """Configure google.generativeai SDK for direct API access."""
    if not HAS_GENAI:
        return False
    try:
        api_key = get_google_api_key()
        genai.configure(api_key=api_key)
        return True
    except ValueError as e:
        print(f"Error: {e}")
        return False


def _build_genai_content(prompt: str, image_path: Optional[str]):
    """Build content argument for google.generativeai SDK calls."""
    if image_path:
        from PIL import Image  # type: ignore[import]
        return [prompt, Image.open(image_path)]
    return prompt


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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
    Invoke Gemini model with a text (or multi-modal) prompt.

    Routes through Cloudflare AI Gateway when proxy.env is configured;
    falls back to direct Google API via google-generativeai SDK.

    Args:
        prompt: The text prompt to send
        model: Model name (default: gemini-2.0-flash-exp)
        temperature: Sampling temperature (0.0–1.0)
        max_output_tokens: Maximum tokens in response
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        image_path: Optional path to image file for multi-modal input

    Returns:
        Response text if successful, None if error
    """
    if model not in MODELS:
        raise ValueError(f"Invalid model: {model}. Choose from {list(MODELS.keys())}")

    model_id = MODELS[model]
    cf_creds = get_cf_credentials()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if cf_creds and HAS_REQUESTS:
                # --- Cloudflare AI Gateway path ---
                contents = _build_contents(prompt, image_path)
                gen_cfg: dict = {"temperature": temperature}
                if max_output_tokens:
                    gen_cfg["maxOutputTokens"] = max_output_tokens
                if top_p is not None:
                    gen_cfg["topP"] = top_p
                if top_k is not None:
                    gen_cfg["topK"] = top_k

                response = _cf_request(model_id, contents, gen_cfg, cf_creds)
                return _extract_text(response)

            else:
                # --- Direct SDK path ---
                if not _initialize_direct_client():
                    return None

                gen_cfg_sdk = {"temperature": temperature}
                if max_output_tokens:
                    gen_cfg_sdk["max_output_tokens"] = max_output_tokens
                if top_p is not None:
                    gen_cfg_sdk["top_p"] = top_p
                if top_k is not None:
                    gen_cfg_sdk["top_k"] = top_k

                model_instance = genai.GenerativeModel(
                    model_name=model_id,
                    generation_config=gen_cfg_sdk,
                )
                content = _build_genai_content(prompt, image_path)
                response = model_instance.generate_content(content)
                return response.text

        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                print(f"Error invoking Gemini: {e}")
                return None

    return None


def invoke_with_structured_output(
    prompt: str,
    pydantic_model: Type,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    image_path: Optional[str] = None,
) -> Optional[object]:
    """
    Invoke Gemini with structured (JSON schema) output using a Pydantic model.

    Args:
        prompt: The text prompt to send
        pydantic_model: Pydantic model class for response schema
        model: Model name (default: gemini-2.0-flash-exp)
        temperature: Sampling temperature (0.0–1.0)
        image_path: Optional path to image file for multi-modal input

    Returns:
        Instance of pydantic_model if successful, None if error
    """
    if not HAS_PYDANTIC:
        print("Error: pydantic not installed. Run: uv pip install pydantic")
        return None

    if model not in MODELS:
        raise ValueError(f"Invalid model: {model}. Choose from {list(MODELS.keys())}")

    model_id = MODELS[model]
    cf_creds = get_cf_credentials()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if cf_creds and HAS_REQUESTS:
                # --- Cloudflare AI Gateway path ---
                contents = _build_contents(prompt, image_path)
                schema = _pydantic_to_schema(pydantic_model)
                gen_cfg = {
                    "temperature": temperature,
                    "responseMimeType": "application/json",
                    "responseSchema": schema,
                }
                response = _cf_request(model_id, contents, gen_cfg, cf_creds)
                text = _extract_text(response)
                if text:
                    json_data = json.loads(text)
                    return pydantic_model(**json_data)

            else:
                # --- Direct SDK path ---
                if not _initialize_direct_client():
                    return None

                model_instance = genai.GenerativeModel(
                    model_name=model_id,
                    generation_config={
                        "temperature": temperature,
                        "response_mime_type": "application/json",
                        "response_schema": pydantic_model,
                    },
                )
                content = _build_genai_content(prompt, image_path)
                response = model_instance.generate_content(content)
                json_data = json.loads(response.text)
                return pydantic_model(**json_data)

        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                print(f"Error invoking Gemini with structured output: {e}")
                return None

    return None


def invoke_parallel(
    prompts: list,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_workers: int = 5,
) -> list:
    """
    Invoke Gemini with multiple prompts in parallel.

    Args:
        prompts: List of text prompts to process
        model: Model name (default: gemini-2.0-flash-exp)
        temperature: Sampling temperature (0.0–1.0)
        max_workers: Maximum concurrent requests

    Returns:
        List of response strings (None for failed requests) in prompt order
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: list = [None] * len(prompts)

    def _process(idx: int, prompt: str):
        return idx, invoke_gemini(prompt, model=model, temperature=temperature)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process, idx, prompt): idx
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


def get_available_models() -> list:
    """Return list of registered Gemini model names."""
    return list(MODELS.keys())


def verify_setup() -> bool:
    """
    Verify that Gemini client is properly configured.

    Returns:
        True if at least one credential source is valid and a test call succeeds
    """
    cf_creds = get_cf_credentials()
    if cf_creds:
        print(f"Using Cloudflare AI Gateway (account: {cf_creds['CF_ACCOUNT_ID'][:8]}...)")
    elif HAS_GENAI:
        if not _initialize_direct_client():
            return False
        print("Using direct Google API (google-generativeai SDK)")
    else:
        print("Error: no credentials configured and google-generativeai not installed")
        return False

    try:
        test_response = invoke_gemini("Say 'OK'", model=DEFAULT_MODEL)
        return test_response is not None
    except Exception as e:
        print(f"Setup verification failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("Gemini Client Self-Test")
    print("=" * 50)

    cf = get_cf_credentials()
    if cf:
        print(f"Backend: Cloudflare AI Gateway ({cf['CF_ACCOUNT_ID'][:8]}.../{cf['CF_GATEWAY_ID']})")
    elif HAS_GENAI:
        print("Backend: Direct Google API (google-generativeai SDK)")
    else:
        print("ERROR: no credentials and google-generativeai not installed")
        sys.exit(1)

    print("\n1. Verifying setup...")
    if verify_setup():
        print("   ✓ Setup verified")
    else:
        print("   ✗ Setup failed")
        sys.exit(1)

    print("\n2. Available models:")
    for name in get_available_models():
        print(f"   - {name}")

    print("\n3. Testing basic invocation...")
    resp = invoke_gemini("What is 2+2? Answer in one word.", model=DEFAULT_MODEL)
    if resp:
        print(f"   Response: {resp.strip()}")
    else:
        print("   ✗ Invocation failed")
        sys.exit(1)

    if HAS_PYDANTIC:
        print("\n4. Testing structured output...")
        from pydantic import BaseModel as PM, Field

        class MathAnswer(PM):
            result: int = Field(description="The numerical result")
            explanation: str = Field(description="Brief explanation")

        structured = invoke_with_structured_output(
            prompt="What is 5+7? Provide result and explanation.",
            pydantic_model=MathAnswer,
            model=DEFAULT_MODEL,
        )
        if structured:
            print(f"   Result: {structured.result}")
            print(f"   Explanation: {structured.explanation}")
        else:
            print("   ✗ Structured output failed")

    print("\n5. Testing parallel invocation...")
    test_prompts = [
        "Capital of France? One word.",
        "Capital of Japan? One word.",
        "Capital of Brazil? One word.",
    ]
    parallel_results = invoke_parallel(test_prompts, model=DEFAULT_MODEL)
    for prompt, result in zip(test_prompts, parallel_results):
        status = result.strip() if result else "Failed"
        print(f"   {prompt[:35]}... → {status}")

    print("\n" + "=" * 50)
    print("Self-test complete!")
