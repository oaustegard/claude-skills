#!/usr/bin/env python3
"""
Integration Test for orchestrating-agents skill

This script demonstrates:
1. Simple single invocation
2. Parallel multi-perspective analysis
3. Error handling when key is missing
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from claude_client import (
    invoke_claude,
    invoke_parallel,
    invoke_claude_streaming,
    invoke_parallel_streaming,
    invoke_parallel_interruptible,
    InterruptToken,
    ClaudeInvocationError
)


def test_simple_invocation():
    """Test 1: Simple single invocation"""
    print("=" * 60)
    print("TEST 1: Simple Single Invocation")
    print("=" * 60)

    try:
        response = invoke_claude(
            prompt="What is the capital of France? Answer in 5 words or less.",
            max_tokens=50
        )
        print(f"\n✓ Response: {response}\n")
        return True
    except Exception as e:
        print(f"\n✗ Failed: {e}\n")
        return False


def test_parallel_analysis():
    """Test 2: Parallel multi-perspective analysis"""
    print("=" * 60)
    print("TEST 2: Parallel Multi-Perspective Analysis")
    print("=" * 60)

    # Simulated code snippet for analysis
    code_snippet = """
def authenticate_user(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = db.execute(query)
    return result
"""

    prompts = [
        {
            "prompt": f"Analyze this code from a SECURITY perspective. List top 2 issues:\n\n{code_snippet}",
            "system": "You are a security expert. Be concise.",
            "temperature": 0.3
        },
        {
            "prompt": f"Analyze this code from a CORRECTNESS perspective. List top 2 issues:\n\n{code_snippet}",
            "system": "You are a software quality expert. Be concise.",
            "temperature": 0.3
        },
        {
            "prompt": f"Analyze this code from a MAINTAINABILITY perspective. List top 2 issues:\n\n{code_snippet}",
            "system": "You are a software architecture expert. Be concise.",
            "temperature": 0.3
        },
        {
            "prompt": f"Analyze this code from a PERFORMANCE perspective. List top 2 issues:\n\n{code_snippet}",
            "system": "You are a performance optimization expert. Be concise.",
            "temperature": 0.3
        }
    ]

    try:
        print("\nInvoking 4 parallel analyses...")
        print("Perspectives: Security, Correctness, Maintainability, Performance\n")

        responses = invoke_parallel(prompts, max_tokens=300, max_workers=4)

        perspectives = ["Security", "Correctness", "Maintainability", "Performance"]

        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)

        for perspective, response in zip(perspectives, responses):
            print(f"\n### {perspective.upper()} PERSPECTIVE ###")
            print(response)
            print("-" * 60)

        print("\n✓ Parallel analysis completed successfully!\n")
        return True

    except Exception as e:
        print(f"\n✗ Failed: {e}\n")
        return False


def test_error_handling():
    """Test 3: Error handling demonstration"""
    print("=" * 60)
    print("TEST 3: Error Handling")
    print("=" * 60)

    # Test with invalid parameters
    test_cases = [
        {
            "name": "Empty prompt",
            "params": {"prompt": "", "max_tokens": 10},
            "expected_error": ValueError
        },
        {
            "name": "Invalid max_tokens",
            "params": {"prompt": "Test", "max_tokens": 0},
            "expected_error": ValueError
        },
        {
            "name": "Invalid temperature",
            "params": {"prompt": "Test", "temperature": 2.0},
            "expected_error": ValueError
        }
    ]

    all_passed = True

    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}...")
        try:
            invoke_claude(**test_case['params'])
            print(f"  ✗ Should have raised {test_case['expected_error'].__name__}")
            all_passed = False
        except test_case['expected_error'] as e:
            print(f"  ✓ Correctly raised {type(e).__name__}: {e}")
        except Exception as e:
            print(f"  ✗ Unexpected error: {type(e).__name__}: {e}")
            all_passed = False

    if all_passed:
        print("\n✓ All error handling tests passed!\n")
    else:
        print("\n✗ Some error handling tests failed!\n")

    return all_passed


def test_streaming():
    """Test streaming functionality."""
    print("=" * 60)
    print("TEST 5: Streaming Functionality")
    print("=" * 60)

    try:
        response = invoke_claude_streaming(
            "Say hello",
            callback=lambda c: None  # Silent callback
        )
        assert len(response) > 0
        print("\n✓ Streaming test passed!\n")
        return True
    except Exception as e:
        print(f"\n✗ Failed: {e}\n")
        return False


def test_parallel_streaming():
    """Test parallel streaming."""
    print("=" * 60)
    print("TEST 6: Parallel Streaming")
    print("=" * 60)

    try:
        results = invoke_parallel_streaming([
            {"prompt": "Say hello"},
            {"prompt": "Say goodbye"}
        ])
        assert len(results) == 2
        print(f"\n✓ Results: {results}\n")
        return True
    except Exception as e:
        print(f"\n✗ Failed: {e}\n")
        return False


def test_interruptible():
    """Test interruptible parallel."""
    print("=" * 60)
    print("TEST 7: Interruptible Parallel")
    print("=" * 60)

    try:
        token = InterruptToken()
        results = invoke_parallel_interruptible(
            [{"prompt": "Say hello"}],
            interrupt_token=token
        )
        assert len(results) == 1
        print(f"\n✓ Results: {results}\n")
        return True
    except Exception as e:
        print(f"\n✗ Failed: {e}\n")
        return False


def test_credentials_fallback():
    """Test 4: Credentials system check"""
    print("=" * 60)
    print("TEST 4: Credentials System Check")
    print("=" * 60)

    try:
        # Import credentials module
        api_creds_path = Path(__file__).parent.parent.parent / "api-credentials" / "scripts"
        sys.path.append(str(api_creds_path))
        from credentials import get_anthropic_api_key, get_api_key_masked

        # Test key retrieval
        print("\nAttempting to retrieve API key...")
        key = get_anthropic_api_key()
        masked = get_api_key_masked()

        print(f"✓ API key found: {masked}")
        print(f"  Key length: {len(key)} characters")
        print(f"  Source: config.json or environment variable\n")
        return True

    except ValueError as e:
        print(f"\n⚠ No API key configured:")
        print(f"  {e}\n")
        print("This is expected if you haven't set up credentials yet.")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}\n")
        return False


def main():
    """Run all integration tests"""
    print("\n" + "=" * 60)
    print("ORCHESTRATING-AGENTS SKILL INTEGRATION TESTS")
    print("=" * 60)
    print()

    # Check credentials first
    has_credentials = test_credentials_fallback()

    if not has_credentials:
        print("\n" + "!" * 60)
        print("SKIPPING API TESTS - No credentials configured")
        print("!" * 60)
        print("\nTo run full tests, configure API credentials:")
        print("1. Copy config.json.example to config.json")
        print("2. Add your Anthropic API key")
        print("3. Run this script again")
        print()
        return

    # Run error handling tests (don't need API)
    test_error_handling()

    # Run API tests
    results = {
        "Simple Invocation": test_simple_invocation(),
        "Parallel Analysis": test_parallel_analysis(),
        "Streaming": test_streaming(),
        "Parallel Streaming": test_parallel_streaming(),
        "Interruptible": test_interruptible(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠ Some tests failed.")

    print("=" * 60)
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
