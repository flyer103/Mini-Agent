"""Browser automation tool using Playwright for web interaction.

This module provides various browser automation tools for web interaction, including navigation,
clicking, typing, screenshots, and more.

## Special Notes for Complex Websites (Gmail, SPA, etc.)

For complex websites like Gmail, Single Page Applications (SPA), or sites with JavaScript
 event interception, use the following approach:

1. **For Gmail email list items**: Use `browser_js_click` instead of `browser_click`
   - Gmail uses JavaScript event interception that can block standard clicks
   - browser_js_click uses JavaScript's dispatchEvent to bypass interceptors

2. **For elements requiring hover**: Use `browser_hover` before clicking
   - Some elements (like Gmail labels) become interactive only after hovering
   - Example: browser_hover(selector=".label-item") then browser_click(selector=".label-item")

3. **Troubleshooting clicks that don't work**:
   - Try browser_js_click instead of browser_click
   - Use browser_inspect to check element visibility and click handlers
   - Take screenshots to visually inspect the page state

4. **Gmail-specific usage pattern**:
   ```
   browser_goto(url="https://mail.google.com")
   browser_screenshot(path="./gmail.png")  # Verify loaded state
   browser_js_click(selector="tr[role='row']:nth-child(1)")  # Click first email
   browser_screenshot(path="./email_opened.png")  # Verify opened
   ```
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from playwright.async_api import async_playwright

from .base import Tool, ToolResult

# Suppress Node.js deprecation warnings from Playwright
os.environ["NODE_NO_WARNINGS"] = "1"


_browser_manager = None


def _load_browser_config() -> Dict[str, Any]:
    """Load browser configuration from config files."""
    config = {}

    # Possible config file locations (in priority order)
    config_paths = [
        Path("mini_agent/config/config.yaml"),  # Development mode
        Path.home() / ".mini-agent/config/config.yaml",  # User config directory
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = yaml.safe_load(f)
                    if data and 'tools' in data:
                        browser_options = data['tools'].get('browser_options', {})
                        config['use_existing_browser'] = browser_options.get('use_existing_browser', False)
                        config['cdp_url'] = browser_options.get('cdp_url', 'http://localhost:9222')
                break
            except Exception as e:
                print(f"Warning: Failed to load config from {config_path}: {e}")
                continue

    return config


class BrowserManager:
    """Singleton manager for browser instances."""

    def __init__(self, use_existing_browser=False, cdp_url=None):
        self._playwright = None
        self._browser = None
        self._page = None
        self._playwright_context = None
        self._use_existing_browser = use_existing_browser
        self._cdp_url = cdp_url or "http://localhost:9222"
        self._connected_to_existing = False

    async def ensure_browser(self):
        """Ensure browser is launched and page exists."""
        if self._playwright is None:
            self._playwright_context = async_playwright()
            self._playwright = await self._playwright_context.__aenter__()

        if self._browser is None:
            if self._use_existing_browser:
                # Try to connect to existing browser via CDP
                try:
                    self._browser = await self._playwright.chromium.connect_over_cdp(
                        self._cdp_url
                    )
                    self._connected_to_existing = True
                    print(f"Connected to existing browser at {self._cdp_url}")
                except Exception as e:
                    print(f"Failed to connect to existing browser at {self._cdp_url}: {e}")
                    print("Falling back to launching new browser...")
                    self._browser = await self._playwright.chromium.launch(
                        headless=False,  # Run in visible mode by default
                        args=["--no-sandbox"]
                    )
                    self._connected_to_existing = False
            else:
                # Launch new browser
                self._browser = await self._playwright.chromium.launch(
                    headless=False,  # Run in visible mode by default
                    args=["--no-sandbox"]
                )
                self._connected_to_existing = False

        if self._page is None:
            if self._connected_to_existing:
                # When connected to existing browser, use the first page or create new one
                contexts = self._browser.contexts
                if contexts and len(contexts[0].pages) > 0:
                    self._page = contexts[0].pages[0]
                else:
                    self._page = await self._browser.new_page()
            else:
                self._page = await self._browser.new_page()

        return self._page

    async def get_page(self):
        """Get the current page, creating browser if needed."""
        return await self.ensure_browser()

    async def close(self):
        """Close browser and clean up resources."""
        if self._page:
            await self._page.close()
            self._page = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright_context:
            await self._playwright_context.__aexit__(None, None, None)
            self._playwright_context = None
            self._playwright = None

    @property
    def is_active(self) -> bool:
        """Check if browser is active."""
        return self._browser is not None and self._page is not None

    @property
    def is_connected_to_existing(self) -> bool:
        """Check if connected to an existing browser."""
        return self._connected_to_existing

    async def connect_to_existing_browser(self, cdp_url: str = "http://localhost:9222"):
        """
        Connect to an existing browser instance via Chrome DevTools Protocol.

        Args:
            cdp_url: The CDP endpoint URL (default: http://localhost:9222)
        """
        self._cdp_url = cdp_url
        self._use_existing_browser = True

        if self._playwright is None:
            self._playwright_context = async_playwright()
            self._playwright = await self._playwright_context.__aenter__()

        if self._browser is None:
            try:
                self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
                self._connected_to_existing = True
                print(f"Successfully connected to existing browser at {cdp_url}")

                # Get or create a page
                contexts = self._browser.contexts
                if contexts and len(contexts[0].pages) > 0:
                    self._page = contexts[0].pages[0]
                else:
                    self._page = await self._browser.new_page()

                return True
            except Exception as e:
                print(f"Failed to connect to existing browser at {cdp_url}: {e}")
                return False


def get_browser_manager(use_existing_browser=False, cdp_url=None):
    """
    Get the global browser manager instance.

    Args:
        use_existing_browser: Whether to try connecting to an existing browser
        cdp_url: CDP endpoint URL for connecting to existing browser (default: http://localhost:9222)

    Returns:
        BrowserManager instance
    """
    global _browser_manager
    if _browser_manager is None:
        # If no explicit parameters provided, load from config
        if not use_existing_browser and cdp_url is None:
            config = _load_browser_config()
            use_existing_browser = config.get('use_existing_browser', False)
            cdp_url = config.get('cdp_url', 'http://localhost:9222')

            # Print connection mode for debugging
            if use_existing_browser:
                print(f"Browser config: Attempting to connect to existing browser at {cdp_url}")
            else:
                print("Browser config: Launching new browser instance")

        _browser_manager = BrowserManager(use_existing_browser=use_existing_browser, cdp_url=cdp_url)
    return _browser_manager


class BrowserGotoTool(Tool):
    """Navigate to a URL in the browser."""

    @property
    def name(self) -> str:
        return "browser_goto"

    @property
    def description(self) -> str:
        return """Navigate the browser to a specific URL.

Use this tool to open web pages in the browser. The browser will automatically launch if not already running.

Examples:
  - browser_goto(url="https://www.google.com")
  - browser_goto(url="https://github.com")"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to navigate to. Must include protocol (http:// or https://).",
                }
            },
            "required": ["url"],
        }

    async def execute(self, url: str) -> ToolResult:
        """Navigate to the specified URL."""
        try:
            manager = get_browser_manager()
            page = await manager.get_page()

            # Navigate to URL
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Get page info
            title = await page.title()
            current_url = page.url

            return ToolResult(
                success=True,
                content=f"Successfully navigated to: {current_url}\nPage title: {title}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to navigate to URL: {str(e)}"
            )


class BrowserScreenshotTool(Tool):
    """Take a screenshot of the current browser page."""

    @property
    def name(self) -> str:
        return "browser_screenshot"

    @property
    def description(self) -> str:
        return """Take a screenshot of the current browser page and save it to a file.

Use this tool to visually inspect the current state of the web page.

Parameters:
  - path: File path where the screenshot will be saved. Should end with .png

Examples:
  - browser_screenshot(path="./workspace/screenshot.png")"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path where the screenshot will be saved. Should end with .png.",
                }
            },
            "required": ["path"],
        }

    async def execute(self, path: str) -> ToolResult:
        """Take a screenshot and save to file."""
        try:
            from pathlib import Path

            manager = get_browser_manager()
            if not manager.is_active:
                return ToolResult(
                    success=False,
                    error="Browser is not active. Navigate to a URL first using browser_goto."
                )

            page = await manager.get_page()

            # Ensure directory exists
            screenshot_path = Path(path)
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)

            # Take screenshot
            await page.screenshot(path=str(screenshot_path), full_page=True)

            return ToolResult(
                success=True,
                content=f"Screenshot saved to: {screenshot_path.absolute()}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to take screenshot: {str(e)}"
            )


class BrowserGetContentTool(Tool):
    """Get the content (text) of the current page."""

    @property
    def name(self) -> str:
        return "browser_get_content"

    @property
    def description(self) -> str:
        return """Extract and return the visible text content from the current page.

This tool retrieves all visible text from the page, which is useful for understanding the page content without taking a screenshot.

Examples:
  - browser_get_content()"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> ToolResult:
        """Get page content."""
        try:
            manager = get_browser_manager()
            if not manager.is_active:
                return ToolResult(
                    success=False,
                    error="Browser is not active. Navigate to a URL first using browser_goto."
                )

            page = await manager.get_page()

            # Get visible text content
            content = await page.evaluate("""
                () => {
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        {
                            acceptNode: function(node) {
                                const element = node.parentElement;
                                if (!element) return NodeFilter.FILTER_REJECT;

                                const style = window.getComputedStyle(element);
                                if (style.display === 'none' ||
                                    style.visibility === 'hidden' ||
                                    style.opacity === '0') {
                                    return NodeFilter.FILTER_REJECT;
                                }
                                return NodeFilter.FILTER_ACCEPT;
                            }
                        }
                    );

                    const textNodes = [];
                    let node;
                    while (node = walker.nextNode()) {
                        const text = node.textContent.trim();
                        if (text.length > 0) {
                            textNodes.push(text);
                        }
                    }

                    return textNodes.join('\\n');
                }
            """)

            # Also get title and URL
            title = await page.title()
            url = page.url

            result = f"URL: {url}\nTitle: {title}\n\nContent:\n{content}"

            return ToolResult(
                success=True,
                content=result
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get page content: {str(e)}"
            )


class BrowserClickTool(Tool):
    """Click an element on the page using a CSS selector."""

    @property
    def name(self) -> str:
        return "browser_click"

    @property
    def description(self) -> str:
        return """Click an element on the current page using a CSS selector.

Use this tool to interact with buttons, links, and other clickable elements. If you're not sure about the selector, use browser_screenshot or browser_get_content first to inspect the page.

IMPORTANT: For complex websites like Gmail or sites with JavaScript event interception,
use browser_js_click instead of browser_click. browser_js_click uses JavaScript's dispatchEvent
which bypasses many event interceptors.

Parameters:
  - selector: CSS selector to identify the element to click
  - wait_for: Optional selector to wait for after clicking (e.g., a new page element)

Examples:
  - browser_click(selector="button.submit")
  - browser_click(selector="a.login", wait_for=".dashboard")
  - browser_click(selector="#search-button")

Note: For Gmail email items, use browser_js_click(selector="tr[role='row']:nth-child(1)")"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to identify the element to click. For example: button.submit, a.login, #search-button",
                },
                "wait_for": {
                    "type": "string",
                    "description": "Optional CSS selector to wait for after clicking (useful for page navigation or dynamic content).",
                }
            },
            "required": ["selector"],
        }

    async def execute(self, selector: str, wait_for: str | None = None) -> ToolResult:
        """Click an element."""
        try:
            manager = get_browser_manager()
            if not manager.is_active:
                return ToolResult(
                    success=False,
                    error="Browser is not active. Navigate to a URL first using browser_goto."
                )

            page = await manager.get_page()

            # Wait for and click the element
            await page.wait_for_selector(selector, timeout=5000)
            await page.click(selector)

            # Wait for navigation or element if specified
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=5000)

            # Get updated page info
            title = await page.title()

            return ToolResult(
                success=True,
                content=f"Successfully clicked element: {selector}\nCurrent page: {title}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to click element '{selector}': {str(e)}"
            )


class BrowserTypeTool(Tool):
    """Type text into an input field."""

    @property
    def name(self) -> str:
        return "browser_type"

    @property
    def description(self) -> str:
        return """Type text into an input field on the current page.

Use this tool to fill out forms and input fields.

Parameters:
  - selector: CSS selector for the input field
  - text: Text to type into the field
  - clear_first: Whether to clear the field before typing (default: true)

Examples:
  - browser_type(selector="#username", text="myuser")
  - browser_type(selector="#search", text="playwright python")
  - browser_type(selector="input[name='email']", text="test@example.com")"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to identify the input field.",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type into the field.",
                },
                "clear_first": {
                    "type": "boolean",
                    "description": "Whether to clear the field before typing.",
                    "default": True,
                }
            },
            "required": ["selector", "text"],
        }

    async def execute(self, selector: str, text: str, clear_first: bool = True) -> ToolResult:
        """Type text into an input field."""
        try:
            manager = get_browser_manager()
            if not manager.is_active:
                return ToolResult(
                    success=False,
                    error="Browser is not active. Navigate to a URL first using browser_goto."
                )

            page = await manager.get_page()

            # Wait for and focus the element
            await page.wait_for_selector(selector, timeout=5000)

            if clear_first:
                await page.fill(selector, "")

            await page.type(selector, text)

            return ToolResult(
                success=True,
                content=f"Successfully typed text into: {selector}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to type into field '{selector}': {str(e)}"
            )


class BrowserInspectTool(Tool):
    """Inspect element properties and state on the current page."""

    @property
    def name(self) -> str:
        return "browser_inspect"

    @property
    def description(self) -> str:
        return """Inspect an element's properties and state using a CSS selector.

This tool checks if an element exists, is visible, is enabled, and provides other useful information.
Use this to debug why an element might not be clickable.

Parameters:
  - selector: CSS selector for the element to inspect

Examples:
  - browser_inspect(selector="a.login")
  - browser_inspect(selector="button.submit")
  - browser_inspect(selector="[data-name='foo']")"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to identify the element to inspect.",
                }
            },
            "required": ["selector"],
        }

    async def execute(self, selector: str) -> ToolResult:
        """Inspect element properties."""
        try:
            manager = get_browser_manager()
            if not manager.is_active:
                return ToolResult(
                    success=False,
                    error="Browser is not active. Navigate to a URL first using browser_goto."
                )

            page = await manager.get_page()

            # Evaluate element properties
            properties = await page.evaluate(f"""
                (selector) => {{
                    const element = document.querySelector(selector);
                    if (!element) {{
                        return null;
                    }}

                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);

                    return {{
                        exists: true,
                        tagName: element.tagName,
                        id: element.id,
                        className: element.className,
                        innerText: element.textContent?.substring(0, 200),
                        isVisible: style.display !== 'none' &&
                                  style.visibility !== 'hidden' &&
                                  style.opacity !== '0' &&
                                  rect.width > 0 &&
                                  rect.height > 0,
                        isEnabled: !element.disabled,
                        rect: {{
                            top: rect.top,
                            left: rect.left,
                            width: rect.width,
                            height: rect.height,
                            bottom: rect.bottom,
                            right: rect.right
                        }},
                        zIndex: style.zIndex,
                        position: style.position,
                        pointerEvents: style.pointerEvents,
                        hasClickHandler: typeof element.onclick !== 'undefined',
                        attributes: Array.from(element.attributes).map(attr => ({{
                            name: attr.name,
                            value: attr.value
                        }}))
                    }};
                }}
            """, selector)

            if properties is None:
                return ToolResult(
                    success=False,
                    error=f"Element not found: '{selector}'"
                )

            # Format properties for display
            result = f"Element: {selector}\n"
            result += f"Tag: {properties['tagName']}\n"
            result += f"ID: {properties['id'] or 'none'}\n"
            result += f"Classes: {properties['className'] or 'none'}\n"
            result += f"Visible: {properties['isVisible']}\n"
            result += f"Enabled: {properties['isEnabled']}\n"
            result += f"Dimensions: {properties['rect']['width']}x{properties['rect']['height']} at ({properties['rect']['left']}, {properties['rect']['top']})\n"
            result += f"Pointer events: {properties['pointerEvents']}\n"
            result += f"Has click handler: {properties['hasClickHandler']}\n"
            result += f"\nText content: {properties['innerText'][:100]}...\n"

            if properties['attributes']:
                result += "\nAttributes:\n"
                for attr in properties['attributes'][:10]:  # Show first 10 attributes
                    result += f"  {attr['name']}: {attr['value'][:100]}\n"

            return ToolResult(
                success=True,
                content=result
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to inspect element '{selector}': {str(e)}"
            )


class BrowserHoverTool(Tool):
    """Hover over an element on the page using a CSS selector."""

    @property
    def name(self) -> str:
        return "browser_hover"

    @property
    def description(self) -> str:
        return """Hover over an element on the current page using a CSS selector.

Some elements (like Gmail labels) require hovering before they become interactive.
Use this tool before clicking such elements.

Parameters:
  - selector: CSS selector to identify the element to hover

Examples:
  - browser_hover(selector=".label-item")
  - browser_hover(selector="[data-name='foo']")"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to identify the element to hover. For example: .label-item, [data-name='foo']",
                }
            },
            "required": ["selector"],
        }

    async def execute(self, selector: str) -> ToolResult:
        """Hover over an element."""
        try:
            manager = get_browser_manager()
            if not manager.is_active:
                return ToolResult(
                    success=False,
                    error="Browser is not active. Navigate to a URL first using browser_goto."
                )

            page = await manager.get_page()

            # Wait for element and hover
            await page.wait_for_selector(selector, timeout=5000)
            await page.hover(selector)

            return ToolResult(
                success=True,
                content=f"Successfully hovered over element: {selector}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to hover over element '{selector}': {str(e)}"
            )


class BrowserJavaScriptClickTool(Tool):
    """Click an element using JavaScript (bypasses some click interception)."""

    @property
    def name(self) -> str:
        return "browser_js_click"

    @property
    def description(self) -> str:
        return """Click an element using JavaScript execution (useful when normal clicks fail).

This uses JavaScript's dispatchEvent to trigger a click, which can bypass some click
interceptors and work in cases where the element is covered by other elements.

Parameters:
  - selector: CSS selector to identify the element to click

Examples:
  - browser_js_click(selector=".label-item")
  - browser_js_click(selector="[data-name='foo']")"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to identify the element to click. For example: .label-item, [data-name='foo']",
                }
            },
            "required": ["selector"],
        }

    async def execute(self, selector: str) -> ToolResult:
        """Click an element using JavaScript."""
        try:
            manager = get_browser_manager()
            if not manager.is_active:
                return ToolResult(
                    success=False,
                    error="Browser is not active. Navigate to a URL first using browser_goto."
                )

            page = await manager.get_page()

            # Wait for element
            await page.wait_for_selector(selector, timeout=5000)

            # Click using JavaScript
            await page.evaluate(f"""
                (selector) => {{
                    const element = document.querySelector(selector);
                    if (!element) {{
                        throw new Error('Element not found');
                    }}
                    element.dispatchEvent(new MouseEvent('click', {{
                        bubbles: true,
                        cancelable: true,
                        view: window
                    }}));
                }}
            """, selector)

            return ToolResult(
                success=True,
                content=f"Successfully clicked element using JavaScript: {selector}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to JavaScript-click element '{selector}': {str(e)}"
            )


class BrowserCloseTool(Tool):
    """Close the browser and clean up resources."""

    @property
    def name(self) -> str:
        return "browser_close"

    @property
    def description(self) -> str:
        return """Close the browser and clean up all resources.

Use this tool when you're done with browser automation to free up system resources.

Examples:
  - browser_close()"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self) -> ToolResult:
        """Close the browser."""
        try:
            manager = get_browser_manager()
            await manager.close()

            return ToolResult(
                success=True,
                content="Browser closed successfully."
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to close browser: {str(e)}"
            )
