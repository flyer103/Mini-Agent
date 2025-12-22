"""Test script to diagnose Gmail Labels clicking issue."""

import asyncio
from mini_agent import Agent
from mini_agent.tools.browser_tool import BrowserManager

async def inspect_gmail_labels():
    """Inspect Gmail Labels section to understand the structure."""
    print("Launching browser and navigating to Gmail...")

    agent = Agent()
    await agent.initialize()

    # Navigate to Gmail
    result = await agent.run("browser_goto", url="https://mail.google.com")
    print(f"\n=== Navigation Result ===\n{result}\n")

    # Wait for user to login if needed
    print("Please login to Gmail if needed, then press Enter to continue...")
    input()

    # Take screenshot
    result = await agent.run("browser_screenshot", path="./workspace/gmail_labels.png")
    print(f"\n=== Screenshot Result ===\n{result}\n")

    # Get page content to see Labels
    result = await agent.run("browser_get_content")
    print(f"\n=== Page Content (partial) ===\n")
    # Print only lines containing "Label" to avoid too much output
    lines = result.split('\n')
    for line in lines:
        if 'abel' in line.lower() or '收件箱' in line or 'inbox' in line.lower():
            print(line)
    print("... (check full content in output above)\n")

    # Try to find Labels section using JavaScript evaluation
    manager = BrowserManager()
    page = await manager.get_page()

    print("=== Inspecting Gmail DOM Structure ===\n")

    js_code = """
    () => {
        const results = [];

        // Find all elements that might be Labels
        const possibleLabelElements = document.querySelectorAll('[role="navigation"], [data-tooltip], .aim, [data-name]');

        for (let el of possibleLabelElements) {
            const text = el.textContent.trim();
            if (text && text.length < 100) { // Only capture reasonable text length
                results.push({
                    tag: el.tagName,
                    className: el.className,
                    id: el.id,
                    role: el.getAttribute('role'),
                    dataTooltip: el.getAttribute('data-tooltip'),
                    dataName: el.getAttribute('data-name'),
                    innerText: text.substring(0, 100),
                    isVisible: el.offsetWidth > 0 && el.offsetHeight > 0,
                    hasClick: typeof el.onclick !== 'undefined' || el.tagName === 'A' || el.tagName === 'BUTTON'
                });
            }
        }

        return results;
    }
    """

    try:
        elements = await page.evaluate(js_code)
        print("Found potentially relevant elements:\n")
        for i, el in enumerate(elements[:20]):  # Show first 20
            print(f"{i}. {el.tag} | class: '{el.className}' | text: '{el.innerText}' | visible: {el.isVisible}")
            if (el.dataTooltip):
                print(f"   data-tooltip: {el.dataTooltip}")
            if (el.dataName):
                print(f"   data-name: {el.dataName}")
            print()
    except Exception as e:
        print(f"Error evaluating JS: {e}")

    await agent.close()

if __name__ == "__main__":
    asyncio.run(inspect_gmail_labels())
