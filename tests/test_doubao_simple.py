#!/usr/bin/env python3
"""Simple test to debug Doubao multi-turn conversation issue."""

import asyncio
import os

from mini_agent.llm.llm_wrapper import LLMClient
from mini_agent.schema import LLMProvider, Message


async def debug_conversation():
    """Debug multi-turn conversation step by step."""
    print("=== Debug Doubao Multi-turn Conversation ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    model = os.getenv("DOUBAO_MODEL")

    if not api_key or not model:
        print("Error: Environment variables not set")
        return

    llm = LLMClient(
        api_key=api_key,
        provider=LLMProvider.DOUBAO,
        model=model,
    )

    # First turn
    print("Step 1: First message")
    messages = [
        Message(role="user", content="中国的首都是哪个城市？"),
    ]
    print(f"  Messages to send: {[(m.role, m.content[:30]) for m in messages]}")

    try:
        response = await llm.generate(messages)
        print(f"  ✓ Success! Response: {response.content[:50]}")
        print(f"  ✓ Token usage: {response.usage.total_tokens}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return

    print()

    # Add response to history
    messages.append(Message(role="assistant", content=response.content))
    messages.append(Message(role="user", content="那里有什么著名的景点？"))

    print("Step 2: Second message (with history)")
    print(f"  Messages to send: {[(m.role, m.content[:30]) for m in messages]}")

    try:
        response = await llm.generate(messages)
        print(f"  ✓ Success! Response: {response.content[:50]}")
        print(f"  ✓ Token usage: {response.usage.total_tokens}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        print(f"  Error type: {type(e).__name__}")

    print()

    # Let's also test a simple follow-up without full history
    print("Step 3: Simple follow-up (no full history)")
    simple_messages = [
        Message(role="user", content="那里有什么著名的景点？"),
    ]
    print(f"  Messages to send: {[(m.role, m.content[:30]) for m in simple_messages]}")

    try:
        response = await llm.generate(simple_messages)
        print(f"  ✓ Success! Response: {response.content[:50]}")
        print(f"  ✓ Token usage: {response.usage.total_tokens}")
    except Exception as e:
        print(f"  ✗ Error: {e}")


async def test_single_call():
    """Test a single call with simple message."""
    print("=== Test Single Call ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    model = os.getenv("DOUBAO_MODEL")

    llm = LLMClient(
        api_key=api_key,
        provider=LLMProvider.DOUBAO,
        model=model,
    )

    messages = [
        Message(role="user", content="What is the capital of China?"),
    ]

    try:
        response = await llm.generate(messages)
        print(f"✓ Success! Response: {response.content}")
        print(f"✓ Token usage: {response.usage}")
    except Exception as e:
        print(f"✗ Error: {e}")


async def main():
    """Main function."""
    await debug_conversation()
    print()
    print("=" * 60)
    print()
    await test_single_call()


if __name__ == "__main__":
    asyncio.run(main())
