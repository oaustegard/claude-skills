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
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Single Claude API call. Returns response text."""
    headers = {
        "x-api-key": _get_api_key(),
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
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
    model: str = "claude-sonnet-4-6",
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
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
    max_workers: int = 5,
) -> list[str]:
    """
    Run multiple prompts in parallel. Each prompt dict has:
      - prompt: str (user message)
      - system: str (system message)
      - temperature: float (optional, default 0.3)

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
