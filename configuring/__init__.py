"""
configuring: Universal configuration management for AI agent environments.

Usage:
    import sys
    sys.path.insert(0, '/path/to/claude-skills')
    from configuring import get_env, detect_environment

    token = get_env("MY_TOKEN", required=True)
    env = detect_environment()  # "claude.ai", "claude-code-desktop", etc.
"""

from .scripts.getting_env import (
    __version__,
    debug_info,
    detect_environment,
    get_env,
    get_loaded_sources,
    load_all,
    load_env,
    mask_secret,
)

__all__ = [
    "__version__",
    "debug_info",
    "detect_environment",
    "get_env",
    "get_loaded_sources",
    "load_all",
    "load_env",
    "mask_secret",
]
