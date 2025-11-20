#!/usr/bin/env python3
"""Test interrupt functionality."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import threading
import time
from claude_client import invoke_parallel_interruptible, InterruptToken

def test_interrupt():
    """Test interrupting parallel operations."""
    print("=== Test: Interrupt ===")

    token = InterruptToken()

    # Create long-running prompts
    prompts = [
        {"prompt": f"Write a long essay about topic {i}"}
        for i in range(5)
    ]

    def run_analysis():
        results = invoke_parallel_interruptible(
            prompts,
            interrupt_token=token
        )
        return results

    # Start in background
    thread = threading.Thread(target=run_analysis)
    thread.start()

    # Interrupt after 2 seconds
    print("Starting analysis...")
    time.sleep(2)
    print("\nInterrupting...")
    token.interrupt()

    thread.join(timeout=5)
    print("✓ Interrupt test completed")


if __name__ == "__main__":
    test_interrupt()
