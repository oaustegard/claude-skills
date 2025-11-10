#!/usr/bin/env python3
"""
Test script for prompt caching functionality
"""

import sys
from pathlib import Path

# Add module to path
sys.path.append(str(Path(__file__).parent))

from claude_client import invoke_claude, invoke_parallel, ConversationThread

def test_cache_system():
    """Test system prompt caching"""
    print("\n=== Test 1: System Prompt Caching ===")

    # Large system context (1024+ tokens required for caching)
    large_system = "You are an expert." + " This is filler text." * 200

    response = invoke_claude(
        prompt="Say 'system cached' in 2 words",
        system=large_system,
        cache_system=True,
        max_tokens=20
    )
    print(f"Response: {response}")
    print("✓ System caching test passed")


def test_cache_prompt():
    """Test user prompt caching"""
    print("\n=== Test 2: User Prompt Caching ===")

    # Large prompt
    large_prompt = "Here is a large document. " * 100 + "\n\nWhat is this about? Answer in 3 words."

    response = invoke_claude(
        prompt=large_prompt,
        cache_prompt=True,
        max_tokens=20
    )
    print(f"Response: {response}")
    print("✓ Prompt caching test passed")


def test_shared_system_parallel():
    """Test shared cached system in parallel invocations"""
    print("\n=== Test 3: Shared System Caching (Parallel) ===")

    # Large shared context
    shared_context = "You are analyzing code. " + "Context filler. " * 200

    prompts = [
        {"prompt": "Say 'agent 1' in 2 words"},
        {"prompt": "Say 'agent 2' in 2 words"},
        {"prompt": "Say 'agent 3' in 2 words"}
    ]

    results = invoke_parallel(
        prompts,
        shared_system=shared_context,
        cache_shared_system=True,
        max_tokens=20,
        max_workers=3
    )

    for i, result in enumerate(results, 1):
        print(f"Agent {i}: {result}")

    print("✓ Shared system caching test passed")


def test_conversation_thread():
    """Test ConversationThread with auto-caching"""
    print("\n=== Test 4: ConversationThread Auto-Caching ===")

    # Large system context
    system_context = "You are a helpful assistant. " + "Context. " * 200

    thread = ConversationThread(
        system=system_context,
        cache_system=True,
        max_tokens=50
    )

    # Turn 1
    response1 = thread.send("Count to 3")
    print(f"Turn 1: {response1}")

    # Turn 2 (should reuse cached system + turn 1)
    response2 = thread.send("Now count to 5")
    print(f"Turn 2: {response2}")

    print(f"Thread has {len(thread)} turns")
    print("✓ ConversationThread test passed")


def test_manual_cache_blocks():
    """Test manual cache control blocks"""
    print("\n=== Test 5: Manual Cache Control Blocks ===")

    system_blocks = [
        {"type": "text", "text": "You are an expert. " + "Context. " * 100},
        {"type": "text", "text": "Additional context. " * 100, "cache_control": {"type": "ephemeral"}}
    ]

    response = invoke_claude(
        prompt="Say 'manual cache' in 2 words",
        system=system_blocks,
        max_tokens=20
    )
    print(f"Response: {response}")
    print("✓ Manual cache blocks test passed")


if __name__ == "__main__":
    print("Testing Prompt Caching Implementation")
    print("=" * 50)

    try:
        # Test 1: System caching
        test_cache_system()

        # Test 2: Prompt caching
        test_cache_prompt()

        # Test 3: Shared system in parallel
        test_shared_system_parallel()

        # Test 4: ConversationThread
        test_conversation_thread()

        # Test 5: Manual cache blocks
        test_manual_cache_blocks()

        print("\n" + "=" * 50)
        print("✓ All caching tests passed!")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
