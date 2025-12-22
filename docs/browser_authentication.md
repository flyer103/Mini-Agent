# Browser Authentication with Existing Browser Session

This guide explains how to use Mini Agent with an already-running browser instance to leverage existing authentication sessions, cookies, and logged-in states.

## Overview

By default, Mini Agent launches a new browser instance. However, you can configure it to connect to an existing browser session, which is useful for:

- Accessing authenticated sessions without re-logging in
- Reusing existing cookies and login states
- Working with sites that require authentication
- Testing workflows in the context of a logged-in user
- Preserving browser extensions and user preferences

## How It Works

Mini Agent uses Chrome DevTools Protocol (CDP) to connect to an already-running browser instance. This allows it to reuse the browser's:

- Cookies and session data
- Login/authentication state
- Browser extensions
- User preferences and settings
- Cached data

## Setup Instructions

### Step 1: Launch Browser with Remote Debugging

Close all existing browser windows first, then launch your browser with the `--remote-debugging-port` flag:

#### macOS (Chrome)
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir=$HOME/ChromeProfile/
```

#### macOS (Edge)
```bash
"/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" --remote-debugging-port=9222 --user-data-dir=$HOME/ChromeProfile/
```

#### Linux (Chrome/Chromium)
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=$HOME/ChromeProfile/
# or
chromium-browser --remote-debugging-port=9222 --user-data-dir=$HOME/ChromeProfile/
```

#### Windows (Chrome)
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

#### Windows (Edge)
```cmd
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222
```

### Step 2: Log Into Websites

Navigate to the websites you want to access and log in as you normally would. Mini Agent will be able to reuse these sessions.

### Step 3: Configure Mini Agent

Update your `config.yaml` file to enable connecting to the existing browser:

```yaml
# Browser Connection Settings
browser_options:
  use_existing_browser: true  # Set to true to connect to existing browser
  cdp_url: "http://localhost:9222"  # CDP endpoint (default)
```

Alternatively, you can configure it programmatically:

```python
from mini_agent.tools.browser_tool import get_browser_manager

# Connect to existing browser
manager = get_browser_manager(use_existing_browser=True, cdp_url="http://localhost:9222")
await manager.connect_to_existing_browser("http://localhost:9222")
```

## Usage Examples

### Example 1: Check GitHub Notifications

```python
#!/usr/bin/env python3
import asyncio
from mini_agent import Agent
from mini_agent.llm import AnthropicClient
from mini_agent.tools import (
    BrowserGotoTool,
    BrowserScreenshotTool,
    BrowserGetContentTool,
    ReadTool,
)

async def main():
    # Initialize with browser tools
    llm = AnthropicClient(api_key="your-api-key", model="claude-3-5-sonnet-20241022")

    tools = [
        BrowserGotoTool(),
        BrowserScreenshotTool(),
        BrowserGetContentTool(),
        ReadTool(),
    ]

    agent = Agent(
        llm_client=llm,
        system_prompt="You can access my browser. I'm already logged into GitHub.",
        tools=tools,
        workspace_dir="./workspace",
    )

    # Agent will reuse your GitHub session
    agent.add_user_message("Go to GitHub and check my notifications")
    result = await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 2: Gmail Automation

```python
# The agent can access your Gmail without re-authentication
agent.add_user_message("Check my Gmail inbox and tell me about the latest email")
result = await agent.run()
```

### Example 3: Multi-site Workflow

```python
# Agent can access multiple authenticated sites in sequence
agent.add_user_message("""
1. Go to GitHub and check my pull requests
2. Then go to Gmail and check for any code review notifications
3. Take screenshots of both pages
""")
result = await agent.run()
```

## Important Security Considerations

⚠️ **Security Warning**: Connecting to an existing browser session gives Mini Agent access to:

- All your logged-in accounts and sessions
- Cookies and authentication tokens
- Browser extensions and their data
- Autofill information (if enabled)
- Browsing history (if accessible)

### Best Practices

1. **Use a dedicated browser profile**: Launch browser with `--user-data-dir=/path/to/profile` to isolate sessions
   ```bash
   chrome --remote-debugging-port=9222 --user-data-dir=./agent-profile
   ```

2. **Close sensitive tabs** before connecting Mini Agent

3. **Use for specific tasks only**: Launch browser only when needed, close when done

4. **Don't use your main browser**: Consider using a separate browser installation or profile

5. **Revoke sessions after use**: Log out of sensitive accounts when done

## Troubleshooting

### Connection Failed

**Problem**: Mini Agent can't connect to the browser

**Solutions**:
1. Ensure browser was launched with `--remote-debugging-port=9222`
2. Check that port 9222 is not blocked by firewall
3. Verify no other process is using port 9222
4. Ensure browser is still running

### Session Not Reused

**Problem**: Mini Agent launches a new browser instead of connecting

**Solutions**:
1. Verify `use_existing_browser: true` is set in config
2. Check CDP URL matches the launch command
3. Ensure config file is in correct location
4. Confirm browser was launched before starting Mini Agent

### Authentication Issues

**Problem**: Websites still ask for login despite existing session

**Solutions**:
1. Check that you logged in AFTER launching with remote debugging
2. Verify you're using the correct browser profile
3. Some sites may require re-authentication for automation
4. Check if cookies are being blocked or cleared

### Port Already in Use

**Problem**: Error about port 9222 already being used

**Solutions**:
1. Find and kill the process using the port:
   ```bash
   # macOS/Linux
   lsof -ti:9222 | xargs kill -9

   # Windows
   netstat -ano | findstr :9222
   taskkill /PID <PID> /F
   ```
2. Use a different port: `--remote-debugging-port=9333`
3. Update config.yaml with the new port

## Advanced Configuration

### Custom CDP Endpoint

```yaml
browser_options:
  use_existing_browser: true
  cdp_url: "http://localhost:9333"  # Custom port
```

### Using with Different Browsers

Most Chromium-based browsers work:
- Google Chrome
- Microsoft Edge
- Chromium
- Brave (with some limitations)

### Running Headless with Existing Session

Not recommended - headless mode typically can't reuse GUI browser sessions effectively.

## Example: Complete Workflow

See [examples/08_browser_with_existing_session.py](../examples/08_browser_with_existing_session.py) for a complete working example.

```bash
# 1. Launch browser with remote debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# 2. Log into websites

# 3. Run the example
python examples/08_browser_with_existing_session.py
```

## Limitations

1. **Browser must be Chromium-based** (Chrome, Edge, Chromium)
2. **Browser must be launched with remote debugging flag**
3. **Session persistence depends on browser settings** - some sites may still expire sessions
4. **Not all browser extensions work** with CDP automation
5. **File downloads may be handled differently** compared to normal browsing
6. **Certain browser features** may behave differently under CDP control

## Technical Details

Mini Agent uses Playwright's `connect_over_cdp()` method to connect to the browser. This connects via Chrome DevTools Protocol, which is the same protocol used by:

- Chrome Developer Tools
- Puppeteer
- Selenium WebDriver (ChromeDriver)

The connection allows full control over the browser while preserving the user's session state.
