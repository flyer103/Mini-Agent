"""Core Agent implementation with optional LaMer-inspired Meta-RL capabilities."""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional, AsyncIterator

import tiktoken

from .exceptions import ToolTimeoutError
from .llm import LLMClient
from .logger import AgentLogger
from .progress import ProgressIndicator
from .schema import LLMResponse, Message
from .tools.base import Tool, ToolResult
from .utils import calculate_display_width


# LaMer imports (only loaded when enabled)
try:
    from .reflection import ReflectionSystem, MetaLearningSystem, ExecutionEpisode
    LAMER_AVAILABLE = True
except ImportError:
    LAMER_AVAILABLE = False


# ANSI color codes
class Colors:
    """Terminal color definitions"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


class Agent:
    """Agent with basic tools, MCP support, and optional LaMer-inspired reflection and meta-learning capabilities."""

    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str,
        tools: list[Tool],
        max_steps: int = 50,
        workspace_dir: str = "./workspace",
        token_limit: int = 80000,  # Summary triggered when tokens exceed this value
        enable_reflection: bool = False,
        enable_meta_learning: bool = False,
    ):
        self.llm = llm_client
        self.tools = {tool.name: tool for tool in tools}
        self.max_steps = max_steps
        self.token_limit = token_limit
        self.workspace_dir = Path(workspace_dir)

        # Ensure workspace exists
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # LaMer configuration
        self.enable_reflection = enable_reflection and LAMER_AVAILABLE
        self.enable_meta_learning = enable_meta_learning and LAMER_AVAILABLE

        # Initialize LaMer systems if enabled
        if self.enable_reflection:
            self.reflection_system = ReflectionSystem(
                llm_client,
                reflection_dir=str(self.workspace_dir / "reflections")
            )

        if self.enable_meta_learning:
            self.meta_learning_system = MetaLearningSystem(
                self.reflection_system if self.enable_reflection else None
            )

        # Track current task for episode creation
        self.current_task_description: str = ""
        self.task_start_time: float = 0

        # Inject workspace information into system prompt if not already present
        if "Current Workspace" not in system_prompt:
            workspace_info = f"\n\n## Current Workspace\nYou are currently working in: `{self.workspace_dir.absolute()}`\nAll relative paths will be resolved relative to this directory."
            system_prompt = system_prompt + workspace_info

        # Inject LaMer capabilities into system prompt if enabled
        if self.enable_reflection or self.enable_meta_learning:
            from .lamer_config import LAMER_SYSTEM_PROMPT_ADDITIONS
            system_prompt += LAMER_SYSTEM_PROMPT_ADDITIONS

        self.system_prompt = system_prompt

        # Initialize message history
        self.messages: list[Message] = [Message(role="system", content=system_prompt)]

        # Initialize logger
        self.logger = AgentLogger()

        # Token usage from last API response (updated after each LLM call)
        self.api_total_tokens: int = 0
        # Flag to skip token check right after summary (avoid consecutive triggers)
        self._skip_next_token_check: bool = False

    def add_user_message(self, content: str):
        """Add a user message to history and track as current task (for LaMer)."""
        self.current_task_description = content
        self.task_start_time = time.time()
        self.messages.append(Message(role="user", content=content))

    def _estimate_tokens(self) -> int:
        """Accurately calculate token count for message history using tiktoken

        Uses cl100k_base encoder (GPT-4/Claude/M2 compatible)
        """
        try:
            # Use cl100k_base encoder (used by GPT-4 and most modern models)
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback: if tiktoken initialization fails, use simple estimation
            return self._estimate_tokens_fallback()

        total_tokens = 0

        for msg in self.messages:
            # Count text content
            if isinstance(msg.content, str):
                total_tokens += len(encoding.encode(msg.content))
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict):
                        # Convert dict to string for calculation
                        total_tokens += len(encoding.encode(str(block)))

            # Count thinking
            if msg.thinking:
                total_tokens += len(encoding.encode(msg.thinking))

            # Count tool_calls
            if msg.tool_calls:
                total_tokens += len(encoding.encode(str(msg.tool_calls)))

            # Metadata overhead per message (approximately 4 tokens)
            total_tokens += 4

        return total_tokens

    def _estimate_tokens_fallback(self) -> int:
        """Fallback token estimation method (when tiktoken is unavailable)"""
        total_chars = 0
        for msg in self.messages:
            if isinstance(msg.content, str):
                total_chars += len(msg.content)
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict):
                        total_chars += len(str(block))

            if msg.thinking:
                total_chars += len(msg.thinking)

            if msg.tool_calls:
                total_chars += len(str(msg.tool_calls))

        # Rough estimation: average 2.5 characters = 1 token
        return int(total_chars / 2.5)

    async def _summarize_messages(self):
        """Message history summarization: summarize conversations between user messages when tokens exceed limit

        Strategy (Agent mode):
        - Keep all user messages (these are user intents)
        - Summarize content between each user-user pair (agent execution process)
        - If last round is still executing (has agent/tool messages but no next user), also summarize
        - Structure: system -> user1 -> summary1 -> user2 -> summary2 -> user3 -> summary3 (if executing)

        Summary is triggered when EITHER:
        - Local token estimation exceeds limit
        - API reported total_tokens exceeds limit
        """
        # Skip check if we just completed a summary (wait for next LLM call to update api_total_tokens)
        if self._skip_next_token_check:
            self._skip_next_token_check = False
            return

        estimated_tokens = self._estimate_tokens()

        # Check both local estimation and API reported tokens
        should_summarize = estimated_tokens > self.token_limit or self.api_total_tokens > self.token_limit

        # If neither exceeded, no summary needed
        if not should_summarize:
            return

        print(f"\n{Colors.BRIGHT_YELLOW}📊 Token usage - Local estimate: {estimated_tokens}, API reported: {self.api_total_tokens}, Limit: {self.token_limit}{Colors.RESET}")
        print(f"{Colors.BRIGHT_YELLOW}🔄 Triggering message history summarization...{Colors.RESET}")

        # Find all user message indices (skip system prompt)
        user_indices = [i for i, msg in enumerate(self.messages) if msg.role == "user" and i > 0]

        # Need at least 1 user message to perform summary
        if len(user_indices) < 1:
            print(f"{Colors.BRIGHT_YELLOW}⚠️  Insufficient messages, cannot summarize{Colors.RESET}")
            return

        # Build new message list
        new_messages = [self.messages[0]]  # Keep system prompt
        summary_count = 0

        # Iterate through each user message and summarize the execution process after it
        for i, user_idx in enumerate(user_indices):
            # Add current user message
            new_messages.append(self.messages[user_idx])

            # Determine message range to summarize
            # If last user, go to end of message list; otherwise to before next user
            if i < len(user_indices) - 1:
                next_user_idx = user_indices[i + 1]
            else:
                next_user_idx = len(self.messages)

            # Extract execution messages for this round
            execution_messages = self.messages[user_idx + 1 : next_user_idx]

            # If there are execution messages in this round, summarize them
            if execution_messages:
                summary_text = await self._create_summary(execution_messages, i + 1)
                if summary_text:
                    summary_message = Message(
                        role="user",
                        content=f"[Assistant Execution Summary]\n\n{summary_text}",
                    )
                    new_messages.append(summary_message)
                    summary_count += 1

        # Replace message list
        self.messages = new_messages

        # Skip next token check to avoid consecutive summary triggers
        # (api_total_tokens will be updated after next LLM call)
        self._skip_next_token_check = True

        new_tokens = self._estimate_tokens()
        print(f"{Colors.BRIGHT_GREEN}✓ Summary completed, local tokens: {estimated_tokens} → {new_tokens}{Colors.RESET}")
        print(f"{Colors.DIM}  Structure: system + {len(user_indices)} user messages + {summary_count} summaries{Colors.RESET}")
        print(f"{Colors.DIM}  Note: API token count will update on next LLM call{Colors.RESET}")

    async def _create_summary(self, messages: list[Message], round_num: int) -> str:
        """Create summary for one execution round

        Args:
            messages: List of messages to summarize
            round_num: Round number

        Returns:
            Summary text
        """
        if not messages:
            return ""

        # Build summary content
        summary_content = f"Round {round_num} execution process:\n\n"
        for msg in messages:
            if msg.role == "assistant":
                content_text = msg.content if isinstance(msg.content, str) else str(msg.content)
                summary_content += f"Assistant: {content_text}\n"
                if msg.tool_calls:
                    tool_names = [tc.function.name for tc in msg.tool_calls]
                    summary_content += f"  → Called tools: {', '.join(tool_names)}\n"
            elif msg.role == "tool":
                result_preview = msg.content if isinstance(msg.content, str) else str(msg.content)
                summary_content += f"  ← Tool returned: {result_preview}...\n"

        # Call LLM to generate concise summary
        try:
            summary_prompt = f"""Please provide a concise summary of the following Agent execution process:

{summary_content}

Requirements:
1. Focus on what tasks were completed and which tools were called
2. Keep key execution results and important findings
3. Be concise and clear, within 1000 words
4. Use English
5. Do not include "user" related content, only summarize the Agent's execution process"""

            summary_msg = Message(role="user", content=summary_prompt)
            response = await self.llm.generate(
                messages=[
                    Message(
                        role="system",
                        content="You are an assistant skilled at summarizing Agent execution processes.",
                    ),
                    summary_msg,
                ]
            )

            summary_text = response.content
            print(f"{Colors.BRIGHT_GREEN}✓ Summary for round {round_num} generated successfully{Colors.RESET}")
            return summary_text

        except Exception as e:
            print(f"{Colors.BRIGHT_RED}✗ Summary generation failed for round {round_num}: {e}{Colors.RESET}")
            # Use simple text summary on failure
            return summary_content

    async def run(self) -> str:
        """Execute agent loop with optional reflection and meta-learning capabilities."""
        # Start new run, initialize log file
        self.logger.start_new_run()
        print(f"{Colors.DIM}📝 Log file: {self.logger.get_log_file_path()}{Colors.RESET}")

        # Get exploration guidance if LaMer is enabled
        exploration_guidance = ""
        if self.enable_meta_learning and self.current_task_description:
            exploration_guidance = self.meta_learning_system.get_exploration_guidance(
                self.current_task_description
            )

            # Add exploration guidance to system context if available
            if exploration_guidance:
                guidance_message = Message(
                    role="user",
                    content=f"[Exploration Guidance]\n{exploration_guidance}"
                )
                # Insert after system prompt but before user message
                if len(self.messages) >= 2:
                    self.messages.insert(1, guidance_message)
                else:
                    self.messages.append(guidance_message)

        # Get relevant reflections if LaMer is enabled
        relevant_reflections = []
        if self.enable_reflection and self.current_task_description:
            relevant_reflections = self.reflection_system.get_relevant_reflections(
                self.current_task_description
            )

            # Add reflections to context if available
            if relevant_reflections:
                reflections_text = "[Past Reflections]\n" + "\n".join(
                    f"{i+1}. {ref}" for i, ref in enumerate(relevant_reflections)
                )
                reflections_message = Message(
                    role="user",
                    content=reflections_text
                )
                # Insert after system prompt and any exploration guidance
                insert_pos = 1
                if exploration_guidance:
                    insert_pos = 2
                self.messages.insert(insert_pos, reflections_message)

        step = 0

        # Get timeout configuration (defaults if config not available)
        tool_timeout = getattr(self.llm, 'request_timeout', 30.0)
        enable_progress = True
        if hasattr(self.llm, 'request_timeout'):
            # If request_timeout is > 0, use tool timeout and enable progress
            tool_timeout = max(5.0, self.llm.request_timeout * 0.5)  # Tool timeout defaults to half of LLM timeout
            enable_progress = tool_timeout > 0

        while step < self.max_steps:
            # Check and summarize message history to prevent context overflow
            await self._summarize_messages()

            # Step header with proper width calculation
            BOX_WIDTH = 58
            step_text = f"{Colors.BOLD}{Colors.BRIGHT_CYAN}💭 Step {step + 1}/{self.max_steps}{Colors.RESET}"
            step_display_width = calculate_display_width(step_text)
            padding = max(0, BOX_WIDTH - 1 - step_display_width)  # -1 for leading space

            print(f"\n{Colors.DIM}╭{'─' * BOX_WIDTH}╮{Colors.RESET}")
            print(f"{Colors.DIM}│{Colors.RESET} {step_text}{' ' * padding}{Colors.DIM}│{Colors.RESET}")
            print(f"{Colors.DIM}╰{'─' * BOX_WIDTH}╯{Colors.RESET}")

            # Get tool list for LLM call
            tool_list = list(self.tools.values())

            # Log LLM request and call LLM with Tool objects directly
            self.logger.log_request(messages=self.messages, tools=tool_list)

            try:
                response = await self.llm.generate(messages=self.messages, tools=tool_list)
            except Exception as e:
                # Check if it's a retry exhausted error
                from .retry import RetryExhaustedError

                if isinstance(e, RetryExhaustedError):
                    error_msg = f"LLM call failed after {e.attempts} retries\nLast error: {str(e.last_exception)}"
                    print(f"\n{Colors.BRIGHT_RED}❌ Retry failed:{Colors.RESET} {error_msg}")
                else:
                    error_msg = f"LLM call failed: {str(e)}"
                    print(f"\n{Colors.BRIGHT_RED}❌ Error:{Colors.RESET} {error_msg}")
                return error_msg

            # Accumulate API reported token usage
            if response.usage:
                self.api_total_tokens = response.usage.total_tokens

            # Log LLM response
            self.logger.log_response(
                content=response.content,
                thinking=response.thinking,
                tool_calls=response.tool_calls,
                finish_reason=response.finish_reason,
            )

            # Add assistant message
            assistant_msg = Message(
                role="assistant",
                content=response.content,
                thinking=response.thinking,
                tool_calls=response.tool_calls,
            )
            self.messages.append(assistant_msg)

            # Print thinking if present
            if response.thinking:
                print(f"\n{Colors.BOLD}{Colors.MAGENTA}🧠 Thinking:{Colors.RESET}")
                print(f"{Colors.DIM}{response.thinking}{Colors.RESET}")

            # Print assistant response
            if response.content:
                print(f"\n{Colors.BOLD}{Colors.BRIGHT_BLUE}🤖 Assistant:{Colors.RESET}")
                print(f"{response.content}")

            # Check if task is complete (no tool calls)
            if not response.tool_calls:
                break

            # Execute tool calls
            for tool_call in response.tool_calls:
                tool_call_id = tool_call.id
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments

                # Tool call header
                print(f"\n{Colors.BRIGHT_YELLOW}🔧 Tool Call:{Colors.RESET} {Colors.BOLD}{Colors.CYAN}{function_name}{Colors.RESET}")

                # Arguments (formatted display)
                print(f"{Colors.DIM}   Arguments:{Colors.RESET}")
                # Truncate each argument value to avoid overly long output
                truncated_args = {}
                for key, value in arguments.items():
                    value_str = str(value)
                    if len(value_str) > 200:
                        truncated_args[key] = value_str[:200] + "..."
                    else:
                        truncated_args[key] = value
                args_json = json.dumps(truncated_args, indent=2, ensure_ascii=False)
                for line in args_json.split("\n"):
                    print(f"   {Colors.DIM}{line}{Colors.RESET}")

                # Execute tool with timeout and progress indication
                if function_name not in self.tools:
                    result = ToolResult(
                        success=False,
                        content="",
                        error=f"Unknown tool: {function_name}",
                    )
                else:
                    progress = ProgressIndicator(
                        f"Executing {function_name}", enable_progress
                    )
                    try:
                        tool = self.tools[function_name]
                        async with asyncio.timeout(tool_timeout):
                            progress.start()
                            try:
                                result = await tool.execute(**arguments)
                            finally:
                                progress.stop()
                    except asyncio.TimeoutError:
                        error_msg = f"Tool '{function_name}' timed out after {tool_timeout}s. Consider increasing timeout or breaking task into smaller steps."
                        print(f"\n{Colors.BRIGHT_RED}⚠️  Timeout:{Colors.RESET} {error_msg}")
                        result = ToolResult(
                            success=False,
                            content="",
                            error=error_msg,
                        )
                    except Exception as e:
                        # Catch all exceptions during tool execution, convert to failed ToolResult
                        import traceback

                        error_detail = f"{type(e).__name__}: {str(e)}"
                        error_trace = traceback.format_exc()
                        result = ToolResult(
                            success=False,
                            content="",
                            error=f"Tool execution failed: {error_detail}\n\nTraceback:\n{error_trace}",
                        )

                # Log tool execution result
                self.logger.log_tool_result(
                    tool_name=function_name,
                    arguments=arguments,
                    result_success=result.success,
                    result_content=result.content if result.success else None,
                    result_error=result.error if not result.success else None,
                )

                # Print result
                if result.success:
                    result_text = result.content
                    if len(result_text) > 300:
                        result_text = result_text[:300] + f"{Colors.DIM}...{Colors.RESET}"
                    print(f"{Colors.BRIGHT_GREEN}✓ Result:{Colors.RESET} {result_text}")
                else:
                    print(f"{Colors.BRIGHT_RED}✗ Error:{Colors.RESET} {Colors.RED}{result.error}{Colors.RESET}")

                # Add tool result message
                tool_msg = Message(
                    role="tool",
                    content=result.content if result.success else f"Error: {result.error}",
                    tool_call_id=tool_call_id,
                    name=function_name,
                )
                self.messages.append(tool_msg)

            step += 1

        # Task completed or max steps reached
        if step >= self.max_steps:
            result = f"Task couldn't be completed after {self.max_steps} steps."
            print(f"\n{Colors.BRIGHT_YELLOW}⚠️  {result}{Colors.RESET}")
        else:
            result = response.content if response.content else "Task completed."

        # Generate and store reflections if LaMer is enabled
        if self.enable_reflection:
            success = not (result.startswith("❌") or result.startswith("⚠️") or
                          "couldn't be completed" in result)

            episode = ExecutionEpisode(
                task_description=self.current_task_description,
                messages=self.messages.copy(),
                success=success,
                final_outcome=result,
                execution_time=time.time() - self.task_start_time,
                tools_used=list(set([
                    msg.name for msg in self.messages
                    if msg.role == "tool" and msg.name
                ]))
            )

            # Generate and store reflections
            reflections = await self.reflection_system.add_episode(episode)
            print(f"\n💡 Generated {len(reflections)} reflections for future learning!")

            # Update meta-learning strategies if enabled
            if self.enable_meta_learning:
                # Extract strategy updates from reflections
                strategy_update = {
                    'preferred_tools': episode.tools_used,
                    'reflection_guidance': reflections[:3]  # Top 3 reflections
                }
                task_type = self.meta_learning_system._classify_task_type(
                    self.current_task_description
                )
                self.meta_learning_system.update_exploration_strategy(
                    task_type, strategy_update
                )

        return result

    async def run_streaming(self) -> str:
        """Execute agent loop with streaming responses and optional reflection and meta-learning capabilities."""
        # Start new run, initialize log file
        self.logger.start_new_run()
        print(f"{Colors.DIM}📝 Log file: {self.logger.get_log_file_path()}{Colors.RESET}")

        # Get exploration guidance if LaMer is enabled
        exploration_guidance = ""
        if self.enable_meta_learning and self.current_task_description:
            exploration_guidance = self.meta_learning_system.get_exploration_guidance(
                self.current_task_description
            )

            # Add exploration guidance to system context if available
            if exploration_guidance:
                guidance_message = Message(
                    role="user",
                    content=f"[Exploration Guidance]\n{exploration_guidance}"
                )
                # Insert after system prompt but before user message
                if len(self.messages) >= 2:
                    self.messages.insert(1, guidance_message)
                else:
                    self.messages.append(guidance_message)

        # Get relevant reflections if LaMer is enabled
        relevant_reflections = []
        if self.enable_reflection and self.current_task_description:
            relevant_reflections = self.reflection_system.get_relevant_reflections(
                self.current_task_description
            )

            # Add reflections to context if available
            if relevant_reflections:
                reflections_text = "[Past Reflections]\n" + "\n".join(
                    f"{i+1}. {ref}" for i, ref in enumerate(relevant_reflections)
                )
                reflections_message = Message(
                    role="user",
                    content=reflections_text
                )
                # Insert after system prompt and any exploration guidance
                insert_pos = 1
                if exploration_guidance:
                    insert_pos = 2
                self.messages.insert(insert_pos, reflections_message)

        step = 0

        # Get timeout configuration (defaults if config not available)
        tool_timeout = getattr(self.llm, 'request_timeout', 30.0)
        enable_progress = True
        if hasattr(self.llm, 'request_timeout'):
            # If request_timeout is > 0, use tool timeout and enable progress
            tool_timeout = max(5.0, self.llm.request_timeout * 0.5)  # Tool timeout defaults to half of LLM timeout
            enable_progress = tool_timeout > 0

        while step < self.max_steps:
            # Check and summarize message history to prevent context overflow
            await self._summarize_messages()

            # Step header with proper width calculation
            BOX_WIDTH = 58
            step_text = f"{Colors.BOLD}{Colors.BRIGHT_CYAN}💭 Step {step + 1}/{self.max_steps}{Colors.RESET}"
            step_display_width = calculate_display_width(step_text)
            padding = max(0, BOX_WIDTH - 1 - step_display_width)  # -1 for leading space

            print(f"\n{Colors.DIM}╭{'─' * BOX_WIDTH}╮{Colors.RESET}")
            print(f"{Colors.DIM}│{Colors.RESET} {step_text}{' ' * padding}{Colors.DIM}│{Colors.RESET}")
            print(f"{Colors.DIM}╰{'─' * BOX_WIDTH}╯{Colors.RESET}")

            # Get tool list for LLM call
            tool_list = list(self.tools.values())

            # Log LLM request and call LLM with Tool objects directly
            self.logger.log_request(messages=self.messages, tools=tool_list)

            try:
                # Use streaming to get real-time response
                response_parts = {"content": "", "thinking": "", "tool_calls": []}

                # Process streaming responses
                async for chunk in self.llm.generate_stream(messages=self.messages, tools=tool_list):
                    if chunk.content:
                        response_parts["content"] += chunk.content
                        print(f"{Colors.BRIGHT_BLUE}{chunk.content}{Colors.RESET}", end='')

                    if chunk.thinking:
                        response_parts["thinking"] += chunk.thinking
                        print(f"{Colors.DIM}{chunk.thinking}{Colors.RESET}", end='')

                    if chunk.tool_calls:
                        response_parts["tool_calls"].extend(chunk.tool_calls)

                # Create response from aggregated parts
                response = LLMResponse(
                    content=response_parts["content"],
                    thinking=response_parts["thinking"] if response_parts["thinking"] else None,
                    tool_calls=response_parts["tool_calls"] if response_parts["tool_calls"] else None,
                    finish_reason="stop",  # Since we're streaming, this is always "stop"
                    usage=None,  # For now, streaming responses won't include usage
                )

                print()  # New line after streaming is done

            except Exception as e:
                # Check if it's a retry exhausted error
                from .retry import RetryExhaustedError

                if isinstance(e, RetryExhaustedError):
                    error_msg = f"LLM call failed after {e.attempts} retries\nLast error: {str(e.last_exception)}"
                    print(f"\n{Colors.BRIGHT_RED}❌ Retry failed:{Colors.RESET} {error_msg}")
                else:
                    error_msg = f"LLM call failed: {str(e)}"
                    print(f"\n{Colors.BRIGHT_RED}❌ Error:{Colors.RESET} {error_msg}")
                return error_msg

            # Accumulate API reported token usage (only available for non-streaming for now)
            if response.usage:
                self.api_total_tokens = response.usage.total_tokens

            # Log LLM response
            self.logger.log_response(
                content=response.content,
                thinking=response.thinking,
                tool_calls=response.tool_calls,
                finish_reason=response.finish_reason,
            )

            # Add assistant message
            assistant_msg = Message(
                role="assistant",
                content=response.content,
                thinking=response.thinking,
                tool_calls=response.tool_calls,
            )
            self.messages.append(assistant_msg)

            # The content was already shown during streaming, no need to repeat

            # Check if task is complete (no tool calls)
            if not response.tool_calls:
                break

            # Execute tool calls
            for tool_call in response.tool_calls:
                tool_call_id = tool_call.id
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments

                # Tool call header
                print(f"\n{Colors.BRIGHT_YELLOW}🔧 Tool Call:{Colors.RESET} {Colors.BOLD}{Colors.CYAN}{function_name}{Colors.RESET}")

                # Arguments (formatted display)
                print(f"{Colors.DIM}   Arguments:{Colors.RESET}")
                # Truncate each argument value to avoid overly long output
                truncated_args = {}
                for key, value in arguments.items():
                    value_str = str(value)
                    if len(value_str) > 200:
                        truncated_args[key] = value_str[:200] + "..."
                    else:
                        truncated_args[key] = value
                args_json = json.dumps(truncated_args, indent=2, ensure_ascii=False)
                for line in args_json.split("\n"):
                    print(f"   {Colors.DIM}{line}{Colors.RESET}")

                # Execute tool with timeout and progress indication
                if function_name not in self.tools:
                    result = ToolResult(
                        success=False,
                        content="",
                        error=f"Unknown tool: {function_name}",
                    )
                else:
                    progress = ProgressIndicator(
                        f"Executing {function_name}", enable_progress
                    )
                    try:
                        tool = self.tools[function_name]
                        async with asyncio.timeout(tool_timeout):
                            progress.start()
                            try:
                                result = await tool.execute(**arguments)
                            finally:
                                progress.stop()
                    except asyncio.TimeoutError:
                        error_msg = f"Tool '{function_name}' timed out after {tool_timeout}s. Consider increasing timeout or breaking task into smaller steps."
                        print(f"\n{Colors.BRIGHT_RED}⚠️  Timeout:{Colors.RESET} {error_msg}")
                        result = ToolResult(
                            success=False,
                            content="",
                            error=f"Tool execution failed: {error_msg}",
                        )
                    except Exception as e:
                        # Catch all exceptions during tool execution, convert to failed ToolResult
                        import traceback

                        error_detail = f"{type(e).__name__}: {str(e)}"
                        error_trace = traceback.format_exc()
                        result = ToolResult(
                            success=False,
                            content="",
                            error=f"Tool execution failed: {error_detail}\n\nTraceback:\n{error_trace}",
                        )

                # Log tool execution result
                self.logger.log_tool_result(
                    tool_name=function_name,
                    arguments=arguments,
                    result_success=result.success,
                    result_content=result.content if result.success else None,
                    result_error=result.error if not result.success else None,
                )

                # Print result
                if result.success:
                    result_text = result.content
                    if len(result_text) > 300:
                        result_text = result_text[:300] + f"{Colors.DIM}...{Colors.RESET}"
                    print(f"{Colors.BRIGHT_GREEN}✓ Result:{Colors.RESET} {result_text}")
                else:
                    print(f"{Colors.BRIGHT_RED}✗ Error:{Colors.RESET} {Colors.RED}{result.error}{Colors.RESET}")

                # Add tool result message
                tool_msg = Message(
                    role="tool",
                    content=result.content if result.success else f"Error: {result.error}",
                    tool_call_id=tool_call_id,
                    name=function_name,
                )
                self.messages.append(tool_msg)

            step += 1

        # Task completed or max steps reached
        if step >= self.max_steps:
            result = f"Task couldn't be completed after {self.max_steps} steps."
            print(f"\n{Colors.BRIGHT_YELLOW}⚠️  {result}{Colors.RESET}")
        else:
            result = response.content if response.content else "Task completed."

        # Generate and store reflections if LaMer is enabled
        if self.enable_reflection:
            success = not (result.startswith("❌") or result.startswith("⚠️") or
                          "couldn't be completed" in result)

            episode = ExecutionEpisode(
                task_description=self.current_task_description,
                messages=self.messages.copy(),
                success=success,
                final_outcome=result,
                execution_time=time.time() - self.task_start_time,
                tools_used=list(set([
                    msg.name for msg in self.messages
                    if msg.role == "tool" and msg.name
                ]))
            )

            # Generate and store reflections
            reflections = await self.reflection_system.add_episode(episode)
            print(f"\n💡 Generated {len(reflections)} reflections for future learning!")

            # Update meta-learning strategies if enabled
            if self.enable_meta_learning:
                # Extract strategy updates from reflections
                strategy_update = {
                    'preferred_tools': episode.tools_used,
                    'reflection_guidance': reflections[:3]  # Top 3 reflections
                }
                task_type = self.meta_learning_system._classify_task_type(
                    self.current_task_description
                )
                self.meta_learning_system.update_exploration_strategy(
                    task_type, strategy_update
                )

        return result

    def get_history(self) -> list[Message]:
        """Get message history."""
        return self.messages.copy()
