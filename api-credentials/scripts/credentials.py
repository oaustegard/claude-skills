"""
API Credentials Management Module

Provides secure retrieval of Anthropic API keys from config files or environment variables.
"""

import json
import os
from pathlib import Path


def get_anthropic_api_key() -> str:
    """
    Retrieves the Anthropic API key from available sources.

    Priority order:
    1. config.json in the api-credentials skill directory
    2. ANTHROPIC_API_KEY environment variable

    Returns:
        str: The Anthropic API key

    Raises:
        ValueError: If no API key is found in any source
    """
    # Determine the skill directory (parent of scripts/)
    skill_dir = Path(__file__).parent.parent
    config_path = skill_dir / "config.json"

    # Try config.json first
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get('anthropic_api_key', '').strip()
                if api_key:
                    return api_key
        except (json.JSONDecodeError, IOError) as e:
            # If config exists but is malformed, we should know about it
            raise ValueError(
                f"Error reading config.json: {e}\n"
                f"Please check the file at: {config_path}"
            )

    # Try environment variable
    api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if api_key:
        return api_key

    # No key found - provide helpful error message
    raise ValueError(
        "No Anthropic API key found!\n\n"
        "Please configure your API key using one of these methods:\n\n"
        "Option 1: Create config.json\n"
        f"  1. Copy: cp {skill_dir}/assets/config.json.example {skill_dir}/config.json\n"
        f"  2. Edit {skill_dir}/config.json and add your API key\n\n"
        "Option 2: Set environment variable\n"
        "  export ANTHROPIC_API_KEY='sk-ant-api03-...'\n\n"
        "Get your API key from: https://console.anthropic.com/settings/keys"
    )


def get_api_key_masked() -> str:
    """
    Returns a masked version of the API key for logging/display purposes.

    Returns:
        str: Masked API key (e.g., "sk-ant-...xyz")

    Raises:
        ValueError: If no API key is found
    """
    key = get_anthropic_api_key()
    if len(key) > 16:
        return f"{key[:10]}...{key[-4:]}"
    return "***"


if __name__ == "__main__":
    # Test the credential retrieval
    try:
        key = get_anthropic_api_key()
        masked = get_api_key_masked()
        print(f"✓ API key found: {masked}")
        print(f"  Key length: {len(key)} characters")
    except ValueError as e:
        print(f"✗ Error: {e}")
        exit(1)
