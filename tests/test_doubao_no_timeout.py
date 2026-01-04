#!/usr/bin/env python3
"""Test Doubao client without timeout."""

import asyncio
import os

from mini_agent.llm.llm_wrapper import LLMClient
from mini_agent.schema import LLMProvider, Message


async def test_without_timeout():
    """Test without timeout."""
    print("=== Test: No timeout ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    model = os.getenv("DOUBAO_MODEL")

    # Create client without timeout
    llm = LLMClient(
        api_key=api_key,
        provider=LLMProvider.DOUBAO,
        model=model,
        request_timeout=0,  # No timeout, no progress
    )

    for i in range(3):
        print(f"Call {i+1}:")
        try:
            response = await llm.generate([
                Message(role="user", content=f"Test {i+1}")
            ])
            print(f"  ✓ Success: {response.content[:50]}...")
        except Exception as e:
            print(f"  ✗ Error: {e}")


async def test_with_large_timeout():
    """Test with large timeout."""
    print("\n=== Test: Large timeout (300s) ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    model = os.getenv("DOUBAO_MODEL")

    # Create client with large timeout
    llm = LLMClient(
        api_key=api_key,
        provider=LLMProvider.DOUBAO,
        model=model,
        request_timeout=300.0,  # Large timeout
    )

    for i in range(3):
        print(f"Call {i+1}:")
        try:
            response = await llm.generate([
                Message(role="user", content=f"Test {i+1}")
            ])
            print(f"  ✓ Success: {response.content[:50]}...")
        except Exception as e:
            print(f"  ✗ Error: {e}")


async def test_with_retry_disabled():
    """Test with retry disabled."""
    print("\n=== Test: Retry disabled ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    model = os.getenv("DOUBAO_MODEL")

    # Create client with retry disabled
    from mini_agent.retry import RetryConfig

    retry_config = RetryConfig(enabled=False)

    llm = LLMClient(
        api_key=api_key,
        provider=LLMProvider.DOUBAO,
        model=model,
        retry_config=retry_config,
    )

    for i in range(3):
        print(f"Call {i+1}:")
        try:
            response = await llm.generate([
                Message(role="user", content=f"Test {i+1}")
            ])
            print(f"  ✓ Success: {response.content[:50]}...")
        except Exception as e:
            print(f"  ✗ Error: {e}")


async def main():
    """Main function."""
    await test_without_timeout()
    await test_with_large_timeout()
    await test_with_retry_disabled()


if __name__ == "__main__":
    asyncio.run(main())
