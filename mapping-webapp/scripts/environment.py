#!/usr/bin/env python3
"""
Environment detection and adaptive batch sizing.

Detects whether running in Claude.ai container, Claude Code on the Web (CCotW),
or local CLI, and adjusts batch size accordingly.
"""

import os
from dataclasses import dataclass


@dataclass
class Environment:
    """Detected runtime environment."""
    name: str          # "claude-ai", "ccotw", "local"
    batch_size: int    # Pages per batch for analysis/verify
    interactive: bool  # Whether to checkpoint interactively


def detect_environment() -> Environment:
    """Detect the current runtime environment and return appropriate settings.

    Returns:
        Environment with auto-detected batch size and interactivity.
    """
    # Claude.ai container: has /mnt/skills/ and short bash timeouts
    if os.path.exists("/mnt/skills/") and os.path.exists("/mnt/user-data/"):
        return Environment(name="claude-ai", batch_size=4, interactive=True)

    # Claude Code on the Web: has /mnt/skills/ but longer execution windows
    if os.path.exists("/mnt/skills/"):
        return Environment(name="ccotw", batch_size=12, interactive=False)

    # Local CLI
    return Environment(name="local", batch_size=0, interactive=False)


def get_batch_size(override: int | None, env: Environment | None = None) -> int:
    """Get the effective batch size.

    Args:
        override: User-specified --batch-size value, or None for auto.
        env: Pre-detected environment, or None to auto-detect.

    Returns:
        Batch size (0 means unbatched / process all at once).
    """
    if override is not None and override > 0:
        return override
    if env is None:
        env = detect_environment()
    return env.batch_size


def batched(items: list, size: int) -> list[list]:
    """Split a list into batches.

    Args:
        items: Items to batch.
        size: Batch size. 0 or negative means single batch (all items).

    Returns:
        List of batches (sublists).
    """
    if size <= 0:
        return [items] if items else []
    return [items[i:i + size] for i in range(0, len(items), size)]
