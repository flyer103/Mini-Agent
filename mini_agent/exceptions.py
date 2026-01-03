"""Custom exceptions for mini_agent."""


class MiniAgentError(Exception):
    """Base exception for mini_agent."""
    pass


class TimeoutError(MiniAgentError):
    """Raised when an operation exceeds its timeout."""

    def __init__(self, operation: str, timeout: float):
        self.operation = operation
        self.timeout = timeout
        super().__init__(f"{operation} timed out after {timeout}s")


class ToolTimeoutError(TimeoutError):
    """Raised when a tool execution times out."""

    def __init__(self, tool_name: str, timeout: float):
        super().__init__(f"Tool '{tool_name}'", timeout)
        self.tool_name = tool_name


class LLMTimeoutError(TimeoutError):
    """Raised when an LLM API call times out."""

    def __init__(self, timeout: float):
        super().__init__("LLM API call", timeout)
