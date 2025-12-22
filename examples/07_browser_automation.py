#!/usr/bin/env python3
"""
Example: Browser automation with Mini Agent

This example demonstrates how to use the browser tools to automate web interactions.
The agent can navigate to websites, click elements, type into forms, take screenshots,
and extract page content.
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

    print("Browser Automation Example")
    print("=" * 50)
    print("\nThis example demonstrates browser automation capabilities.")
    print("The agent can:\n")
    print("  - Navigate to websites")
    print("  - Take screenshots")
    print("  - Extract page content")
    print("  - Click elements and fill forms")
    print("  - Automate multi-step workflows")
    print("\n" + "=" * 50)

    while True:
        try:
            print("\nEnter a task for the agent (or 'quit' to exit):")
            print("Examples:")
            print('  - "Search for Playwright documentation"')
            print('  - "Go to github.com and take a screenshot"')
            print('  - "Search for Claude Code on Google"')
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break

            print("\n" + "-" * 50)
            print("Running agent...")
            print("-" * 50 + "\n")

            # Run agent
            agent.add_user_message(user_input)
            result = await agent.run()

            print("\n" + "-" * 50)
            print("Task completed!")
            print("-" * 50 + "\n")

            # Check if screenshots were created
            screenshots = list(workspace_dir.glob("**/*.png"))
            if screenshots:
                print(f"\n📸 Screenshots saved: {len(screenshots)}")
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
