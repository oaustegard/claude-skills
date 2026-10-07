"""
Minimal Claude API client using httpx. No SDK dependency.

Provides three functions:
  call_claude(prompt, system, ...) → str
  call_claude_json(prompt, system, ...) → dict
  call_parallel(prompts, ...) → list[str]
"""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import httpx
except ImportError:
    raise ImportError("httpx not installed. Install with: pip install httpx")

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

# Sampling parameters (temperature / top_p / top_k): current models (Sonnet 5.5,
# Haiku 5.5, Opus 5.x, Sonnet 5, Opus 4.7/4.8, Fable) return HTTP 400 for any
# non-default value or reject them entirely. Only legacy families accept them.
_LEGACY_SAMPLING_MARKERS = ("-4-6", "-4-5", "-4-1", "-4-2025", "claude-3", "haiku-4-5")


def _accepts_sampling(model: str) -> bool:
    """True only for legacy model families that still accept temperature/top_p/top_k.

    Unknown ids return False: omitting sampling params is always safe.
    """
    m = (model or "").lower()
    return any(marker in m for marker in _LEGACY_SAMPLING_MARKERS)


def _get_api_key() -> str:
    """Resolve API key from env or project files."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    for path in [Path("/mnt/project/claude.env")]:
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip().startswith("API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("\"'")
                    if key:
                        return key
    raise ValueError("No API key found. Set ANTHROPIC_API_KEY or add /mnt/project/claude.env")


def call_claude(
    prompt: str,
    system: str = "",
    model: str = "claude-sonnet-5-5",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Single Claude API call. Returns response text.

    ``temperature`` is ignored (not sent) on current models such as Sonnet 5.5,
    Haiku 5.5 and Opus 5.x, which reject non-default sampling parameters.
    Only text blocks are returned; leading ``thinking`` blocks are skipped.
    """
    headers = {
        "x-api-key": _get_api_key(),
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if _accepts_sampling(model):
        body["temperature"] = temperature
    if system:
        body["system"] = system

    with httpx.Client(timeout=300) as client:
        resp = client.post(API_URL, json=body, headers=headers)
        resp.raise_for_status()

    data = resp.json()
    return "".join(
        block["text"] for block in data.get("content", []) if block.get("type") == "text"
    )


def call_claude_json(
    prompt: str,
    system: str = "",
    model: str = "claude-sonnet-5-5",
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> dict:
    """Call Claude and parse JSON from response. Strips markdown fences."""
    text = call_claude(prompt, system, model, max_tokens, temperature)
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    return json.loads(text)


def call_parallel(
    prompts: list[dict],
    model: str = "claude-sonnet-5-5",
    max_tokens: int = 4096,
    max_workers: int = 5,
) -> list[str]:
    """
    Run multiple prompts in parallel. Each prompt dict has:
      - prompt: str (user message)
      - system: str (system message)
      - temperature: float (optional, default 0.3; ignored on current models)

    Returns list of response strings in same order as input.
    """
    if not prompts:
        return []

    results = [None] * len(prompts)

    def _run(idx: int, p: dict) -> tuple[int, str]:
        text = call_claude(
            prompt=p["prompt"],
            system=p.get("system", ""),
            model=model,
            max_tokens=max_tokens,
            temperature=p.get("temperature", 0.3),
        )
        return idx, text

    with ThreadPoolExecutor(max_workers=min(max_workers, len(prompts))) as pool:
        futures = {pool.submit(_run, i, p): i for i, p in enumerate(prompts)}
        for future in as_completed(futures):
            idx, text = future.result()
            results[idx] = text

    return results
