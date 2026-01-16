"""AST-Grep tool for code structural search, linting, and rewriting."""

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from .base import Tool, ToolResult


class AstGrepTool(Tool):
    """Tool for running ast-grep commands for AST-based code search and manipulation."""

    def __init__(self, workspace_dir: str = "."):
        """Initialize AstGrepTool with workspace directory.

        Args:
            workspace_dir: Base directory for resolving relative paths
        """
        self.workspace_dir = Path(workspace_dir).absolute()

    @property
    def name(self) -> str:
        return "ast_grep"

    @property
    def description(self) -> str:
        return (
            "Run ast-grep commands for AST-based code search, linting, and rewriting. "
            "This tool enables structural code pattern matching using abstract syntax trees. "
            "Available subcommands: 'run' (search), 'check' (lint), 'replace' (rewrite)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "subcommand": {
                    "type": "string",
                    "enum": ["run", "check", "replace"],
                    "description": "Subcommand: 'run' for search, 'check' for lint, 'replace' for rewrite",
                },
                "pattern": {
                    "type": "string",
                    "description": "AST pattern to match (required for 'run' and 'replace')",
                },
                "replacement": {
                    "type": "string",
                    "description": "Replacement pattern (only for 'replace' subcommand)",
                },
                "lang": {
                    "type": "string",
                    "description": "Language filter (e.g., 'typescript', 'python', 'javascript')",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths to search in (defaults to workspace root, searches recursively by default)",
                },
            },
            "required": ["subcommand"],
        }

    async def execute(
        self,
        subcommand: str,
        pattern: str = "",
        replacement: str = "",
        lang: str = "",
        paths: list[str] = [],
    ) -> ToolResult:
        """Execute ast-grep command."""
        try:
            # Verify ast-grep is installed
            try:
                result = subprocess.run(["ast-grep", "--version"], capture_output=True, text=True)
                if result.returncode != 0:
                    return ToolResult(
                        success=False,
                        content="",
                        error="ast-grep is not installed or not available in PATH. Please install ast-grep first.",
                    )
            except FileNotFoundError:
                return ToolResult(
                    success=False,
                    content="",
                    error="ast-grep is not installed or not available in PATH. Please install ast-grep first.",
                )

            # Build command
            cmd = ["ast-grep", subcommand]

            if subcommand in ["run", "replace"] and pattern:
                cmd.extend(["--pattern", pattern])

            if subcommand == "replace" and replacement:
                cmd.extend(["--rewrite", replacement])

            if lang:
                cmd.extend(["--lang", lang])

            # ast-grep searches recursively by default when directories are provided

            # Add paths if provided
            if paths:
                resolved_paths = []
                for path in paths:
                    p = Path(path)
                    if not p.is_absolute():
                        p = self.workspace_dir / p
                    resolved_paths.append(str(p))
                cmd.extend(resolved_paths)
            else:
                # Default to workspace directory
                cmd.append(str(self.workspace_dir))

            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            # Decode output
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            # Format output
            output_parts = []
            if stdout_text.strip():
                output_parts.append(stdout_text.strip())
            if stderr_text.strip():
                output_parts.append(f"[stderr]: {stderr_text.strip()}")

            output = "\n".join(output_parts)
            if not output:
                output = "(no output)"

            # Success if exit code is 0 or 1
            # 0: Successful execution with matches found
            # 1: Successful execution but no matches found (not an error)
            # 2: Actual error occurred
            is_success = process.returncode in [0, 1]  # Both 0 and 1 are successful outcomes
            if process.returncode == 2:
                error_msg = f"Command failed with exit code {process.returncode}\n{stderr_text.strip()}"
                return ToolResult(
                    success=False,
                    content=output,
                    error=error_msg,
                )

            return ToolResult(success=is_success, content=output)

        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Failed to execute ast-grep command: {str(e)}",
            )