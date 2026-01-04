#!/usr/bin/env python3
"""Test parameters passed to Doubao API."""

import asyncio
import os

from openai import AsyncOpenAI


async def test_minimal_params():
    """Test with minimal params."""
    print("=== Test: Minimal params ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL")

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    params = {
        "model": model,
        "messages": [{"role": "user", "content": "Test"}],
    }

    print(f"Params: {params}\n")

    try:
        response = await client.chat.completions.create(**params)
        print(f"✓ Success: {response.choices[0].message.content[:50]}...")
    except Exception as e:
        print(f"✗ Error: {e}")


async def test_with_extra_body():
    """Test with extra_body parameter."""
    print("\n=== Test: With extra_body ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL")

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    params = {
        "model": model,
        "messages": [{"role": "user", "content": "Test"}],
        "extra_body": {"reasoning_split": True},  # This is from OpenAIClient
    }

    print(f"Params: {params}\n")

    try:
        response = await client.chat.completions.create(**params)
        print(f"✓ Success: {response.choices[0].message.content[:50]}...")
    except Exception as e:
        print(f"✗ Error: {e}")


async def test_multiple_calls_with_extra_body():
    """Test multiple calls with extra_body."""
    print("\n=== Test: Multiple calls with extra_body ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL")

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    for i in range(3):
        print(f"Call {i+1}:")
        params = {
            "model": model,
            "messages": [{"role": "user", "content": f"Test {i+1}"}],
            "extra_body": {"reasoning_split": True},
        }

        try:
            response = await client.chat.completions.create(**params)
            print(f"  ✓ Success: {response.choices[0].message.content[:50]}...")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            print(f"  Error type: {type(e).__name__}")


async def test_multiple_calls_minimal():
    """Test multiple calls with minimal params."""
    print("\n=== Test: Multiple calls minimal ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL")

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    for i in range(3):
        print(f"Call {i+1}:")
        params = {
            "model": model,
            "messages": [{"role": "user", "content": f"Test {i+1}"}],
        }

        try:
            response = await client.chat.completions.create(**params)
            print(f"  ✓ Success: {response.choices[0].message.content[:50]}...")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            print(f"  Error type: {type(e).__name__}")


async def main():
    """Main function."""
    await test_minimal_params()
    await test_with_extra_body()
    await test_multiple_calls_with_extra_body()
    await test_multiple_calls_minimal()


if __name__ == "__main__":
    asyncio.run(main())
