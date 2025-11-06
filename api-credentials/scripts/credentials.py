#!/usr/bin/env python3
"""
API Credentials Management

Central module for retrieving API credentials from config file.
Skills should import this module to access external service credentials.
"""

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / "claude" / "config.json"


def _get_credential(key: str) -> Optional[str]:
    """
    Internal helper to retrieve a credential from config.json

    Args:
        key: The credential key to retrieve

    Returns:
        The credential value if found, None otherwise
    """
    try:
        if not CONFIG_PATH.exists():
            return None

        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)

        value = config.get(key)

        # Return None for empty strings
        if value and isinstance(value, str) and value.strip():
            return value.strip()
        return None

    except (json.JSONDecodeError, OSError, KeyError):
        return None


def get_google_api_key() -> Optional[str]:
    """
    Retrieve Google API key for Gemini and other Google services.

    Returns:
        The API key if configured, None otherwise
    """
    return _get_credential('google_api_key')


def get_anthropic_api_key() -> Optional[str]:
    """
    Retrieve Anthropic API key for Claude API.

    Returns:
        The API key if configured, None otherwise
    """
    return _get_credential('anthropic_api_key')


def verify_credential(provider: str) -> bool:
    """
    Verify that a credential is configured.

    Args:
        provider: Provider name ('google', 'anthropic', etc.)

    Returns:
        True if credential exists and is non-empty, False otherwise
    """
    credential_map = {
        'google': get_google_api_key,
        'anthropic': get_anthropic_api_key,
    }

    getter = credential_map.get(provider.lower())
    if not getter:
        return False

    return getter() is not None


def get_config_path() -> Path:
    """
    Get the path to the config.json file.

    Returns:
        Path object for config.json location
    """
    return CONFIG_PATH


if __name__ == "__main__":
    # Self-test
    print(f"Config path: {CONFIG_PATH}")
    print(f"Config exists: {CONFIG_PATH.exists()}")

    providers = ['google', 'anthropic']
    for provider in providers:
        configured = verify_credential(provider)
        print(f"{provider.capitalize()} API configured: {configured}")
