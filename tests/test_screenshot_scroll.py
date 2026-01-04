"""Test script for the enhanced browser screenshot functionality."""

import asyncio
from mini_agent.tools.browser_tool import get_browser_manager


async def test_screenshot_functionality():
    """Test various screenshot modes."""

    print("=" * 60)
    print("Testing Enhanced Screenshot Functionality")
    print("=" * 60)

    # Use browser manager directly
    manager = get_browser_manager()

    try:
        # Navigate to a page
        print("\n1. Navigating to example page...")
        page = await manager.get_page()
        await page.goto("https://example.com", wait_until="load")
        print("   Navigation successful")

        # Test 1: Default screenshot (full page with scroll)
        print("\n2. Taking default screenshot (full page with scroll)...")
        await page.screenshot(path="./workspace/test_fullpage_scroll.png", full_page=True)
        print("   Screenshot saved: ./workspace/test_fullpage_scroll.png")

        # Test 2: Viewport only screenshot
        print("\n3. Taking viewport-only screenshot...")
        await page.screenshot(path="./workspace/test_viewport.png", full_page=False)
        print("   Screenshot saved: ./workspace/test_viewport.png")

        # Test 3: Test scrolling function manually
        print("\n4. Testing scroll-to-load functionality...")
        await page.evaluate("""
            async () => {
                const scrollHeight = document.documentElement.scrollHeight;
                const viewportHeight = window.innerHeight;
                console.log(`Page height: ${scrollHeight}, Viewport height: ${viewportHeight}`);

                // Scroll down step by step
                for (let y = 0; y < scrollHeight; y += viewportHeight) {
                    window.scrollTo(0, y);
                    await new Promise(resolve => setTimeout(resolve, 100));
                }

                // Scroll back to top
                window.scrollTo(0, 0);
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        """)
        await asyncio.sleep(0.5)
        print("   Scroll test completed")

        # Take screenshot after scrolling
        await page.screenshot(path="./workspace/test_after_scroll.png", full_page=True)
        print("   Screenshot after scroll saved: ./workspace/test_after_scroll.png")

        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("Check the ./workspace/ directory for screenshot files.")
        print("=" * 60)

    finally:
        # Clean up
        await manager.close()


if __name__ == "__main__":
    asyncio.run(test_screenshot_functionality())
