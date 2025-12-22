#!/usr/bin/env python3
"""
Example: Browser automation with existing browser session

This example demonstrates how to use Mini Agent with an already-running browser
instance. This is useful for:
- Accessing authenticated sessions
- Reusing cookies and login states
- Working with sites that require authentication
- Avoiding repeated logins

Prerequisites:
1. Chrome, Chromium, or Edge browser installed
2. Browser launched with --remote-debugging-port=9222 flag
3. User logged into target websites before running agent
"""

import asyncio
import os
from pathlib import Path

from mini_agent import Agent
from mini_agent.llm import AnthropicClient
from mini_agent.tools import (
    BrowserClickTool,
    BrowserCloseTool,
    BrowserGetContentTool,
    BrowserGotoTool,
    BrowserScreenshotTool,
    BrowserTypeTool,
    ReadTool,
)


async def main():
    # Create workspace directory
    workspace_dir = Path("./workspace")
    workspace_dir.mkdir(exist_ok=True)

    # Get API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Please set ANTHROPIC_API_KEY environment variable")
        return

    # Initialize LLM client
    llm = AnthropicClient(api_key=api_key, model="claude-3-5-sonnet-20241022")

    # Define system prompt with browser automation context
    system_prompt = """You are a helpful assistant with browser automation capabilities.

You have access to browser tools that allow you to:
1. Navigate to websites (browser_goto)
2. Take screenshots of pages (browser_screenshot)
3. Extract page content/text (browser_get_content)
4. Click elements like buttons and links (browser_click)
5. Type text into input fields (browser_type)
6. Close the browser when done (browser_close)

IMPORTANT: You are connected to an EXISTING browser session with pre-existing:
- Cookies
- Login sessions
- Authenticated states
- User preferences

This means:
- Users may already be logged into websites
- You have access to their authentication state
- DO NOT ask users to log in again
- Work with the existing session

When performing browser automation:
- Always start by navigating to a URL using browser_goto
- Take screenshots at key steps to visually verify the state
- Use browser_get_content to understand page structure
- Interact with elements using appropriate selectors
- Always close the browser when finished with browser_close

Best practices:
- Inspect the page with screenshots or content extraction before clicking
- Use descriptive CSS selectors (IDs, classes, or tag names)
- Clear input fields before typing when appropriate
- Wait for elements to appear after clicking or navigation
- Save screenshots to the workspace for review
"""

    # Create tools
    tools = [
        BrowserGotoTool(),
        BrowserScreenshotTool(),
        BrowserGetContentTool(),
        BrowserClickTool(),
        BrowserTypeTool(),
        BrowserCloseTool(),
        ReadTool(),
    ]

    # Create agent
    agent = Agent(
        llm_client=llm,
        system_prompt=system_prompt,
        tools=tools,
        workspace_dir=str(workspace_dir),
    )

    print("Browser Automation with Existing Session")
    print("=" * 70)
    print("\nThis example demonstrates browser automation using an existing browser.")
    print("\nPREREQUISITES:")
    print("1. Launch browser with remote debugging:")
    print("   macOS:  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
    print("   Linux:  google-chrome --remote-debugging-port=9222")
    print("   Windows: \"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" --remote-debugging-port=9222")
    print("\n2. Log into websites before running this script")
    print("3. The agent will reuse your authentication state\n")
    print("=" * 70)

    print("\n⚠️  WARNING: This script connects to your REAL browser session!")

    while True:
        try:
            print("\nEnter a task for the agent (or 'quit' to exit):")
            print("Examples:")
            print('  - "Go to GitHub and check my notifications"')
            print('  - "Check my Gmail inbox"')
            print('  - "View my recent orders on Amazon"')
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break

            print("\n" + "-" * 70)
            print("Running agent...")
            print("-" * 70 + "\n")

            # Run agent
            agent.add_user_message(user_input)
            result = await agent.run()

            print("\n" + "-" * 70)
            print("Task completed!")
            print("-" * 70 + "\n")

            # Check if screenshots were created
            screenshots = list(workspace_dir.glob("**/*.png"))
            if screenshots:
                print(f"\ud83d\udcf8 Screenshots saved: {len(screenshots)}")
                for screenshot in screenshots:
                    print(f"   - {screenshot.relative_to(workspace_dir)}")

        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")

    # Ensure browser is closed
    manager = None
    try:
        from mini_agent.tools.browser_tool import get_browser_manager
        manager = get_browser_manager()
        await manager.close()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting...")
