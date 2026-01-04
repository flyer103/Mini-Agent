#!/usr/bin/env python3
"""Example: Using Doubao (豆包) LLM with Mini Agent.

This example demonstrates how to use the Doubao LLM from Volcano Engine (火山引擎)
through Mini Agent's unified interface.
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from mini_agent.llm.llm_wrapper import LLMClient
from mini_agent.schema import LLMProvider, Message


async def test_doubao_basic():
    """Test basic chat with Doubao LLM."""
    print("=== Testing Doubao LLM Basic Chat ===\n")

    # Required environment variables:
    # DOUBAO_API_KEY: Your Volcano Engine API key
    # DOUBAO_API_BASE: Optional, default is https://ark.cn-beijing.volces.com/api/v3
    # DOUBAO_MODEL: Optional, model to use (e.g., doubao-pro-32k, doubao-lite-128k)

    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL", "doubao-pro-32k")

    if not api_key:
        print("Error: DOUBAO_API_KEY environment variable not set")
        print("Please set your Volcano Engine API key:")
        print("export DOUBAO_API_KEY='your-api-key'")
        return

    # Initialize LLM client with Doubao provider
    llm = LLMClient(
        api_key=api_key,
        provider=LLMProvider.DOUBAO,
        api_base=api_base,
        model=model,
    )

    # Create messages
    messages = [
        Message(role="user", content="你好！请介绍一下你自己。"),
    ]

    # Generate response
    try:
        response = await llm.generate(messages)
        print(f"Model: {model}")
        print(f"Response: {response.content}")
        if response.usage:
            print(f"Token Usage: {response.usage.total_tokens} total")
            print(f"  - Prompt: {response.usage.prompt_tokens}")
            print(f"  - Completion: {response.usage.completion_tokens}")
        print()
    except Exception as e:
        print(f"Error: {e}")
        print()


async def test_doubao_conversation():
    """Test multi-turn conversation with Doubao LLM."""
    print("=== Testing Doubao LLM Multi-turn Conversation ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    if not api_key:
        return

    llm = LLMClient(
        api_key=api_key,
        provider=LLMProvider.DOUBAO,
        model=os.getenv("DOUBAO_MODEL", "doubao-pro-32k"),
    )

    # First turn
    messages = [
        Message(role="user", content="中国的首都是哪个城市？"),
    ]

    print("User: 中国的首都是哪个城市？")
    response = await llm.generate(messages)
    print(f"Assistant: {response.content}")
    print()

    messages.append(Message(role="assistant", content=response.content))
    messages.append(Message(role="user", content="那里有什么著名的景点？"))

    print("User: 那里有什么著名的景点？")
    response = await llm.generate(messages)
    print(f"Assistant: {response.content}")
    print()


async def test_doubao_english():
    """Test English conversation with Doubao LLM."""
    print("=== Testing Doubao LLM English Conversation ===\n")

    api_key = os.getenv("DOUBAO_API_KEY")
    if not api_key:
        return

    llm = LLMClient(
        api_key=api_key,
        provider=LLMProvider.DOUBAO,
        model=os.getenv("DOUBAO_MODEL", "doubao-pro-32k"),
    )

    messages = [
        Message(
            role="user",
            content="What are the benefits of using AI in software development?"
        ),
    ]

    print("User: What are the benefits of using AI in software development?")
    response = await llm.generate(messages)
    print(f"Assistant: {response.content}")
    print()


async def main():
    """Run all tests."""
    # Load .env file if it exists
    load_dotenv()

    print("=" * 60)
    print("Doubao (豆包) LLM Integration Demo")
    print("=" * 60)
    print()
    print("Prerequisites:")
    print("1. Get API key from Volcano Engine (火山引擎)")
    print("2. Set environment variables:")
    print("   export DOUBAO_API_KEY='your-volcano-engine-api-key'")
    print("   export DOUBAO_MODEL='doubao-pro-32k'  # Optional")
    print("   export DOUBAO_API_BASE='https://ark.cn-beijing.volces.com/api/v3'  # Optional")
    print()
    print("=" * 60)
    print()

    # Run tests
    await test_doubao_basic()
    await test_doubao_conversation()
    await test_doubao_english()

    print("=" * 60)
    print("Demo completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
