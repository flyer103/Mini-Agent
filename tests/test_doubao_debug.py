#!/usr/bin/env python3
"""Debug script for Doubao API connection issues."""

import asyncio
import json
import os
import sys

import aiohttp


async def test_doubao_connection():
    """Test Doubao API connection and print detailed diagnostics."""
    print("=" * 70)
    print("Doubao API Connection Diagnostics")
    print("=" * 70)
    print()

    # Get configuration from environment
    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL", "")

    # Check configuration
    print("Configuration:")
    print(f"  API Key: {'✓ Set' if api_key else '✗ Not set'}")
    print(f"  API Base: {api_base}")
    print(f"  Model / Endpoint ID: {model if model else '✗ Not set'}")
    print()

    if not api_key:
        print("❌ Error: DOUBAO_API_KEY environment variable is not set!")
        print()
        print("Please set your API key:")
        print("  export DOUBAO_API_KEY='your-api-key'")
        return False

    if not model:
        print("❌ Error: DOUBAO_MODEL environment variable is not set!")
        print()
        print("Please set your model/endpoint ID:")
        print("  export DOUBAO_MODEL='ep-xxxxxxxxxx-xxxxx'")
        print()
        print("Note: In Doubao, this should be your Endpoint ID, not model name.")
        print("      You can find it in Volcano Engine console > Model Deployments.")
        return False

    # Test direct API call
    print("Testing API connection...")
    print()

    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 50,
    }

    print("Request details:")
    print(f"  URL: {url}")
    print(f"  Headers: {json.dumps({k: '***' if k == 'Authorization' else v for k, v in headers.items()}, indent=4)}")
    print(f"  Payload: {json.dumps(payload, indent=4)}")
    print()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                print(f"Response Status: {response.status}")
                print()

                if response.status == 200:
                    result = await response.json()
                    print("✅ Success! API call completed.")
                    print()
                    print("Response preview:")
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"  Content: {content[:200]}{'...' if len(content) > 200 else ''}")
                    return True
                elif response.status == 404:
                    print("❌ 404 Not Found Error!")
                    print()
                    print("Possible causes:")
                    print("  1. Incorrect API Base URL")
                    print("  2. Model/Endpoint ID doesn't exist or is not deployed")
                    print("  3. Wrong region (Beijing vs Shanghai)")
                    print()
                    print("Troubleshooting steps:")
                    print()
                    print("  1. Verify your Endpoint ID:")
                    print("     - Go to Volcano Engine console")
                    print("     - Navigate to 'Model Deployments'")
                    print("     - Check that your endpoint is: ACTIVE")
                    print("     - Copy the exact Endpoint ID (starts with 'ep-')")
                    print()
                    print("  2. Verify API Base URL:")
                    print(f"     Current: {api_base}")
                    print("     Should be one of:")
                    print("     - https://ark.cn-beijing.volces.com/api/v3 (Beijing)")
                    print("     - https://ark.cn-shanghai.volces.com/api/v3 (Shanghai)")
                    print()
                    print("  3. Check logs for more details")
                    try:
                        error_text = await response.text()
                        print(f"  Error response: {error_text[:500]}")
                    except:
                        pass
                    return False
                elif response.status == 401:
                    print("❌ 401 Unauthorized Error!")
                    print()
                    print("Your API key is invalid or doesn't have access to this model.")
                    print("Please verify your API key in Volcano Engine console.")
                    return False
                elif response.status == 403:
                    print("❌ 403 Forbidden Error!")
                    print()
                    print("You don't have permission to access this resource.")
                    print("Please check:")
                    print("  - Your API key permissions")
                    print("  - Model deployment status")
                    print("  - Account billing status")
                    return False
                elif response.status == 429:
                    print("❌ 429 Rate Limit Error!")
                    print()
                    print("You have exceeded the rate limit.")
                    print("Please:")
                    print("  - Reduce request frequency")
                    print("  - Upgrade your service tier")
                    print("  - Enable retry logic in config")
                    return False
                else:
                    print(f"❌ Unexpected error: HTTP {response.status}")
                    try:
                        error_text = await response.text()
                        print(f"Error details: {error_text[:500]}")
                    except:
                        pass
                    return False

    except Exception as e:
        print(f"❌ Connection error: {e}")
        print()
        print("Possible causes:")
        print("  - Network connectivity issues")
        print("  - Invalid API base URL")
        print("  - Firewall or proxy blocking the request")
        return False


async def test_with_openai_sdk():
    """Test with OpenAI SDK (as used in DoubaoClient)."""
    print("=" * 70)
    print("Testing with OpenAI SDK (as used in Mini Agent)")
    print("=" * 70)
    print()

    try:
        from openai import AsyncOpenAI
    except ImportError:
        print("❌ OpenAI SDK not installed. Install with:")
        print("   pip install openai")
        return False

    api_key = os.getenv("DOUBAO_API_KEY")
    api_base = os.getenv("DOUBAO_API_BASE", "https://ark.cn-beijing.volces.com/api/v3")
    model = os.getenv("DOUBAO_MODEL", "")

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'Hello from Doubao!'"}],
            max_tokens=50,
        )
        print("✅ OpenAI SDK test successful!")
        print(f"Response: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"❌ OpenAI SDK test failed: {e}")
        print()
        print("Error type:", type(e).__name__)
        return False


def show_configuration_help():
    """Show configuration help."""
    print("=" * 70)
    print("Configuration Guide")
    print("=" * 70)
    print()
    print("1. Set environment variables:")
    print("   export DOUBAO_API_KEY='your-volcano-engine-api-key'")
    print("   export DOUBAO_MODEL='ep-xxxxxxxxxx-xxxxx'  # Your Endpoint ID")
    print("   export DOUBAO_API_BASE='https://ark.cn-beijing.volces.com/api/v3'")
    print()
    print("2. Or configure via config.yaml:")
    print("   api_key: 'your-api-key'")
    print("   provider: 'doubao'")
    print("   api_base: 'https://ark.cn-beijing.volces.com/api/v3'")
    print("   model: 'ep-xxxxxxxxxx-xxxxx'  # Endpoint ID, NOT model name!")
    print()
    print("3. Get your Endpoint ID:")
    print("   - Login to https://console.volcengine.com")
    print("   - Go to 'Model Deployments'")
    print("   - Find your deployed model")
    print("   - Copy the 'Endpoint ID' (starts with 'ep-')")
    print()
    print("   ⚠️  Important: Use Endpoint ID, NOT the model name!")
    print()
    print("4. Verify your deployment:")
    print("   - Status should be: ACTIVE")
    print("   - Region should match your API base URL")
    print("   - Check API key permissions")
    print()


async def main():
    """Main function."""
    show_configuration_help()

    # Run tests
    await test_doubao_connection()
    print()
    print()
    await test_with_openai_sdk()

    print()
    print("=" * 70)
    print("For more help, see: docs/doubao_integration.md")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
