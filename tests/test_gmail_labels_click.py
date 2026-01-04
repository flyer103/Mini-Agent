"""
Example: How to click Gmail Labels using enhanced browser tools.

This demonstrates the proper way to interact with Gmail Labels,
which often require special handling compared to regular clickable elements.
"""

import asyncio
from mini_agent import Agent


async def click_gmail_label(label_name="Important"):
    """
    Example: Click a Gmail Label using various techniques.

    If normal browser_click() doesn't work for Gmail Labels, try:
    1. First inspect the element to understand its properties
    2. Try hovering before clicking
    3. Use JavaScript click as a fallback
    """

    agent = Agent()
    await agent.initialize()

    try:
        print("\n=== Step 1: Navigate to Gmail ===\n")
        result = await agent.run("browser_goto", url="https://mail.google.com")
        print(result)
        print("\nPlease login to Gmail if needed, then press Enter to continue...")
        input()

        print("\n=== Step 2: Take a screenshot to see current state ===\n")
        result = await agent.run("browser_screenshot", path="./workspace/gmail_before.png")
        print(result)

        print("\n=== Step 3: Inspect the label element ===\n")
        # Gmail labels often have data-name or data-tooltip attributes
        # Try different selector patterns:
        selectors_to_try = [
            f"[data-name='{label_name}']",  # Most common
            f"[data-tooltip='{label_name}']",
            f"a[data-name='{label_name}']",
            f"div[data-name='{label_name}']",
        ]

        for selector in selectors_to_try:
            print(f"Trying selector: {selector}")
            result = await agent.run("browser_inspect", selector=selector)
            print(result)
            print()
            if "Visible: True" in str(result):
                break

        print("\n=== Step 4: Try hovering over the element first ===\n")
        result = await agent.run("browser_hover", selector=selectors_to_try[0])
        print(result)

        print("\n=== Step 5: Take screenshot after hover ===\n")
        result = await agent.run("browser_screenshot", path="./workspace/gmail_hover.png")
        print(result)

        print("\n=== Step 6: Try normal click ===\n")
        result = await agent.run("browser_click", selector=selectors_to_try[0])
        print(result)

        print("\n=== Step 7: If normal click fails, use JavaScript click ===\n")
        result = await agent.run("browser_js_click", selector=selectors_to_try[0])
        print(result)

        print("\n=== Step 8: Verify the click worked ===\n")
        result = await agent.run("browser_screenshot", path="./workspace/gmail_after.png")
        print(result)

    finally:
        await agent.close()


async def diagnose_gmail_issues():
    """
    Diagnostic function to find Gmail label selectors and common issues.
    """

    agent = Agent()
    await agent.initialize()

    try:
        print("\n=== Gmail Label Diagnostics ===\n")
        print("Navigating to Gmail...")
        await agent.run("browser_goto", url="https://mail.google.com")

        print("\nPlease login to Gmail, then press Enter...")
        input()

        # Take initial screenshot
        await agent.run("browser_screenshot", path="./workspace/gmail_diagnostic.png")

        # Get page content
        content = await agent.run("browser_get_content")
        print("\n=== Looking for label-related elements ===\n")

        # Extract lines containing potential labels
        lines = str(content).split('\n')
        for line in lines:
            if 'abel' in line.lower() or '收件箱' in line or '收件' in line:
                if len(line.strip()) > 0 and len(line.strip()) < 200:
                    print(line.strip())

    finally:
        await agent.close()


if __name__ == "__main__":
    print("\nGmail Label Clicking Examples")
    print("=" * 50)
    print("\nChoose an option:")
    print("1. Try clicking a specific Gmail Label")
    print("2. Run diagnostics to find label selectors")

    choice = input("\nEnter 1 or 2: ").strip()

    if choice == "1":
        label = input("Which label do you want to click? (e.g., 'Important', 'Sent', 'Drafts'): ").strip()
        asyncio.run(click_gmail_label(label or "Important"))
    elif choice == "2":
        asyncio.run(diagnose_gmail_issues())
    else:
        print("Invalid choice")
