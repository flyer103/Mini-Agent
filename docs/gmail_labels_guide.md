# Gmail Labels Clicking Guide

Gmail Labels in the left sidebar can be tricky to click because Gmail uses complex JavaScript and custom event handling. This guide explains how to use the enhanced browser tools to successfully click Gmail Labels.

## The Problem

When trying to click Gmail Labels with `browser_click()`, you may encounter:
- Timeout errors (element not found)
- Click actions that don't do anything
- "Element is not visible" errors

## Solution: Enhanced Tools

We've added three new tools to help with this:

### 1. **browser_inspect** - Check Element State

Use this first to understand why an element isn't clickable:

```python
result = await agent.run("browser_inspect", selector="[data-name='Important']")
print(result)
```

This will tell you:
- Is the element visible?
- Is it enabled?
- What are its dimensions?
- Does it have click handlers?

### 2. **browser_hover** - Hover Before Clicking

Some Gmail elements (especially Labels) require hovering to become interactive:

```python
# First hover
await agent.run("browser_hover", selector="[data-name='Important']")

# Then click
await agent.run("browser_click", selector="[data-name='Important']")
```

### 3. **browser_js_click** - JavaScript Click (Fallback)

If normal clicks fail, use JavaScript to trigger the click event directly:

```python
result = await agent.run("browser_js_click", selector="[data-name='Important']")
```

This bypasses Playwright's click simulation and uses the browser's native event system.

## Gmail Label Selectors

Gmail Labels typically use these patterns:

```
[data-name='LabelName']           # Most common
[data-tooltip='LabelName']
[title='LabelName']
```

### Finding the Right Selector

1. Login to Gmail
2. Open browser DevTools (F12)
3. Right-click a Label and select "Inspect"
4. Look for `data-name`, `data-tooltip`, or `title` attributes

Common Gmail Label selectors:
```python
selectors = [
    "[data-name='Inbox']",
    "[data-name='Sent']",
    "[data-name='Drafts']",
    "[data-name='Important']",
    "[data-name='Spam']",
    "[data-name='Trash']",
]
```

## Complete Example

```python
from mini_agent import Agent
import asyncio

async def click_gmail_label(label_name="Important"):
    agent = Agent()
    await agent.initialize()

    try:
        # Navigate to Gmail
        await agent.run("browser_goto", url="https://mail.google.com")

        # Try different selector patterns
        selectors = [
            f"[data-name='{label_name}']",
            f"[data-tooltip='{label_name}']",
        ]

        for selector in selectors:
            # First inspect the element
            result = await agent.run("browser_inspect", selector=selector)
            if "Visible: True" in str(result):
                print(f"Found visible element: {selector}")

                # Method 1: Normal click (may work)
                result = await agent.run("browser_click", selector=selector)
                if result.success:
                    print("✓ Click succeeded!")
                    break

                # Method 2: Hover then click (often works)
                await agent.run("browser_hover", selector=selector)
                result = await agent.run("browser_click", selector=selector)
                if result.success:
                    print("✓ Hover + click succeeded!")
                    break

                # Method 3: JavaScript click (fallback)
                result = await agent.run("browser_js_click", selector=selector)
                if result.success:
                    print("✓ JavaScript click succeeded!")
                    break

        await agent.run("browser_screenshot", path="./workspace/result.png")

    finally:
        await agent.close()

# Run it
asyncio.run(click_gmail_label("Important"))
```

## Troubleshooting

### "Element not found" Error
- Try taking a screenshot to verify you're on the right page
- Check if the label name is spelled correctly (case-sensitive)
- Wait longer for Gmail to fully load: `await page.wait_for_timeout(5000)`

### "Element is not visible" Error
- Use `browser_inspect` to check dimensions (should be > 0)
- Gmail may have collapsed the sidebar - try hovering near the left edge first

### Click Has No Effect
- Try `browser_hover` before clicking
- Use `browser_js_click` as a fallback
- Take screenshots before/after to verify state changes

## Best Practices

1. **Always inspect first**: Use `browser_inspect` to verify the element exists and is visible
2. **Hover when needed**: Many Gmail elements require hovering to become interactive
3. **Use JavaScript click as fallback**: When normal clicks fail
4. **Take screenshots**: Helps debug what the browser actually sees
5. **Handle timeouts**: Gmail can be slow to load, increase timeouts if needed

## Run the Test Script

Use the included test script to experiment:

```bash
python test_gmail_labels_click.py
```

This will guide you through:
1. Logging into Gmail
2. Inspecting label elements
3. Trying different clicking methods
4. Taking screenshots at each step
