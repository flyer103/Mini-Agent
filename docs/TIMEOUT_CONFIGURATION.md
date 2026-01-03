# Timeout Configuration Guide

mini_agent now supports configurable timeouts and progress indication to prevent long-running operations from hanging indefinitely.

## Configuration

Add or update the `timeout` section in your `config.yaml`:

```yaml
# ===== Timeout Configuration =====
timeout:
  llm_request: 60.0         # LLM API call timeout (seconds)
  tool_execution: 30.0      # Tool execution timeout (seconds)
  agent_step: 600.0         # Total agent step timeout (seconds) - 10 minutes
  enable_progress: true     # Enable progress indication and status updates
```

### Default Values

- `llm_request`: 60.0 seconds - Controls how long to wait for LLM API responses
- `tool_execution`: 30.0 seconds - Controls execution time for individual tools (bash commands, file operations, etc.)
- `agent_step`: 600.0 seconds (10 minutes) - Not implemented yet (reserved for future use)
- `enable_progress`: true - Enables spinner/progress indicators during long operations

## Features

### 1. LLM API Timeout

LLM API calls (to MiniMax/Anthropic/OpenAI) will timeout after the configured duration.

**When a timeout occurs:**
```
❌ Error: LLM API call timed out after 60s
```

### 2. Tool Execution Timeout

Individual tool executions (bash commands, file operations, etc.) will timeout after the configured duration.

**When a tool times out:**
```
⚠️  Timeout: Tool 'bash' timed out after 30s. Consider increasing timeout or breaking task into smaller steps.
```

### 3. Progress Indication

When `enable_progress: true`, the system shows a spinning indicator during long operations:

```
Waiting for LLM response ⠋ 45.3s
Executing bash ⠙ 12.7s
```

The indicator shows:
- Operation name (e.g., "Waiting for LLM response", "Executing bash")
- Animated spinner (updates every 0.1s)
- Elapsed time in seconds (updates every 0.1s)

## Troubleshooting Timeouts

### If LLM calls timeout too quickly:

Increase `llm_request` in your config:
```yaml
timeout:
  llm_request: 120.0  # Increase to 2 minutes
```

### If tools timeout too quickly:

Increase `tool_execution` in your config:
```yaml
timeout:
  tool_execution: 60.0  # Increase to 1 minute
```

### To disable progress indication:

Set `enable_progress` to false:
```yaml
timeout:
  enable_progress: false
```

### If you prefer no timeouts:

You can disable timeouts by setting values to 0 or very large numbers, but this is not recommended as operations can hang indefinitely.

## Backward Compatibility

If you don't add the `timeout` section to your config, the system will use sensible defaults:
- LLM: 60 seconds
- Tool execution: 30 seconds
- Progress: enabled

All existing configurations work without modification.

## Technical Implementation

The implementation supports:
- Async timeout using `asyncio.wait_for()` and `asyncio.timeout()`
- Non-blocking progress indicators using asyncio tasks
- Graceful timeout error handling with user-friendly error messages
- Default values that don't break existing code

The timeout system is designed to be:
- **User-friendly**: Clear error messages explaining what timed out
- **Non-intrusive**: Progress indicators that don't clutter the output
- **Flexible**: Easy to configure or disable per environment or use case
- **Safe**: Defaults that prevent operations from hanging indefinitely
