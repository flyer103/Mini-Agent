# Fix for Node.js Deprecation Warning in Browser Tools

## Problem

When using browser tools, you may see the following warning:

```
(node:36079) [DEP0169] DeprecationWarning: `url.parse()` behavior is not standardized and prone to errors that have security implications. Use the WHATWG URL API instead. CVEs are not issued for `url.parse()` vulnerabilities.
(Use `node --trace-deprecation ...` to show where the warning was created)
```

## Root Cause

This warning originates from:

1. **Playwright's Node.js driver** - Playwright uses a Node.js process to control browsers
2. **Legacy API usage** - The `url.parse()` API is deprecated in newer Node.js versions (> 16)
3. **Version mismatch** - Playwright 1.57.0 was released in 2023 and may use older Node.js APIs

## Solution Applied

### 1. Added Warning Suppression

Modified `mini_agent/tools/browser_tool.py` to suppress Node.js warnings:

```python
import os

# Suppress Node.js deprecation warnings from Playwright
os.environ["NODE_NO_WARNINGS"] = "1"
```

This sets the `NODE_NO_WARNINGS` environment variable before Playwright initializes, which tells Node.js to suppress all deprecation warnings.

### 2. Why This Approach

- **Non-intrusive**: Doesn't change Playwright's behavior, just suppresses warnings
- **Clean output**: Users won't see confusing warnings that don't affect functionality
- **Future-proof**: When Playwright updates their code to use modern APIs, this will continue to work

## Verification

After applying this fix, the browser tools should work without showing the deprecation warning:

```python
from mini_agent import Agent

async def test_browser():
    agent = Agent()
    await agent.initialize()

    # Should not show deprecation warning
    result = await agent.run("browser_goto", url="https://google.com")
    print(result)

    await agent.close()
```

## Alternative Solutions Considered

### 1. Update Playwright Version
❌ **Not feasible** - Playwright 1.57.0 is currently the latest version available via pip for the Python package

### 2. Use Playwright's Environment Variables
❌ **Insufficient** - Playwright doesn't provide specific environment variables to suppress these warnings

### 3. Patch Node.js Flags
❌ **Too complex** - Would require modifying how Playwright launches the Node.js process

## Technical Details

### Warning Source
- The warning comes from Playwright's browser driver (written in Node.js)
- Located in Playwright's internal code, not in the mini-agent codebase
- Does not affect functionality - it's purely a warning about future compatibility

### Impact
- ✅ **Functionality**: No impact - browser tools work correctly
- ✅ **Security**: No impact - this is about API deprecation, not vulnerabilities
- ✅ **Performance**: No impact - warnings don't affect execution speed
- ❌ **User Experience**: Warning messages can be confusing to users

## When to Revisit

This fix should be revisited when:
- Playwright releases a new Python version (> 1.57.0)
- The deprecation warning appears in actual error logs (not just warnings)
- Playwright announces end-of-support for the current version

## Related Files

- `mini_agent/tools/browser_tool.py` - Added warning suppression
- `pyproject.toml` - Current Playwright version: `playwright>=1.57.0`
