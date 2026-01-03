"""Progress indication utilities for long-running operations."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime


class ProgressIndicator:
    """Manages progress indication for long-running operations."""

    def __init__(self, operation: str, enabled: bool = True):
        self.operation = operation
        self.enabled = enabled
        self.start_time = None
        self._task = None

    async def _show_progress(self):
        """Show periodic progress updates."""
        if not self.enabled:
            return

        # Use simple spinner animation
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        while True:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            print(
                f"\r{self.operation} {spinner[idx % len(spinner)]} {elapsed:.1f}s",
                end="",
                flush=True,
            )
            idx += 1
            await asyncio.sleep(0.1)

    def start(self):
        """Start progress indication."""
        if self.enabled:
            self.start_time = datetime.now()
            self._task = asyncio.create_task(self._show_progress())

    def stop(self):
        """Stop progress indication."""
        if self._task:
            self._task.cancel()
            # Clear the progress line
            print("\r" + " " * 80 + "\r", end="", flush=True)

    @asynccontextmanager
    async def show(self):
        """Context manager for showing progress."""
        self.start()
        try:
            yield self
        finally:
            self.stop()


class StepProgressTracker:
    """Tracks and reports progress across multiple tool executions."""

    def __init__(self, total_tools: int, enabled: bool = True):
        self.total_tools = total_tools
        self.completed_tools = 0
        self.enabled = enabled
        self.start_time = datetime.now()

    def report_progress(self, tool_name: str, status: str):
        """Report progress for a tool."""
        if not self.enabled:
            return

        self.completed_tools += 1
        elapsed = (datetime.now() - self.start_time).total_seconds()

        print(
            f"\r[{self.completed_tools}/{self.total_tools}] {tool_name}: {status} ({elapsed:.1f}s)",
            end="",
            flush=True,
        )

    def finish(self):
        """Clear progress line."""
        if self.enabled:
            print("\r" + " " * 80 + "\r", end="", flush=True)
