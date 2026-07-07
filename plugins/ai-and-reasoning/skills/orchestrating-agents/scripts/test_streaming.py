#!/usr/bin/env python3
"""Test streaming functionality."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from claude_client import invoke_claude_streaming, invoke_parallel_streaming

def test_basic_streaming():
    """Test basic streaming with callback."""
    print("=== Test 1: Basic Streaming ===")

    chunks = []
    def collect_chunk(chunk):
        chunks.append(chunk)
        print(chunk, end='', flush=True)

    response = invoke_claude_streaming(
        "Count from 1 to 5, one number per line.",
        callback=collect_chunk
    )

    print(f"\n\nTotal chunks received: {len(chunks)}")
    print(f"Complete response: {response}")
    assert len(chunks) > 0
    assert response == ''.join(chunks)


def test_parallel_streaming():
    """Test parallel streaming with multiple callbacks."""
    print("\n=== Test 2: Parallel Streaming ===")

    def callback1(chunk):
        print(f"[Agent1] {chunk}", end='', flush=True)

    def callback2(chunk):
        print(f"[Agent2] {chunk}", end='', flush=True)

    results = invoke_parallel_streaming(
        [
            {"prompt": "Say 'Hello from agent 1'"},
            {"prompt": "Say 'Hello from agent 2'"}
        ],
        callbacks=[callback1, callback2]
    )

    print(f"\n\nResults: {results}")
    assert len(results) == 2


if __name__ == "__main__":
    test_basic_streaming()
    test_parallel_streaming()
    print("\n✓ All streaming tests passed")
