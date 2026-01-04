#!/usr/bin/env python3
"""Test Doubao client reuse issue."""

import asyncio
import os

from openai import AsyncOpenAI


async def test_with_new_client_each_time():
    """Test creating new client for each call."""
    print("=== Test: New client for each call ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL")

    for i in range(3):
        print(f"Call {i+1}:")
        try:
            client = AsyncOpenAI(api_key=api_key, base_url=api_base)
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Test {i+1}"}],
                max_tokens=50,
            )
            print(f"  ✓ Success: {response.choices[0].message.content[:50]}...")
        except Exception as e:
            print(f"  ✗ Error: {e}")


async def test_with_reused_client():
    """Test reusing the same client."""
    print("\n=== Test: Reuse client ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL")

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    for i in range(3):
        print(f"Call {i+1}:")
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Test {i+1}"}],
                max_tokens=50,
            )
            print(f"  ✓ Success: {response.choices[0].message.content[:50]}...")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            print(f"  Error type: {type(e).__name__}")


async def test_with_delay():
    """Test with delay between calls."""
    print("\n=== Test: Delay between calls ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL")

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    for i in range(3):
        print(f"Call {i+1}:")
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Test {i+1}"}],
                max_tokens=50,
            )
            print(f"  ✓ Success: {response.choices[0].message.content[:50]}...")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        if i < 2:
            print(f"  Waiting 2 seconds...")
            await asyncio.sleep(2)


async def main():
    """Main function."""
    await test_with_new_client_each_time()
    await asyncio.sleep(1)
    await test_with_reused_client()
    await asyncio.sleep(1)
    await test_with_delay()


if __name__ == "__main__":
    asyncio.run(main())
