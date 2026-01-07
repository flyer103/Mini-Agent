#!/usr/bin/env python3
"""
Mini Agent - Interactive Runtime Example with LaMer Enhanced Capabilities

Usage:
    mini-agent [--workspace DIR] [--lamer]
    mini-agent --help

Examples:
    mini-agent                              # Use current directory as workspace (standard Agent)
    mini-agent --lamer                      # Use LaMer enhanced Agent with reflection and meta-learning
    mini-agent --workspace /path/to/dir     # Use specific workspace directory
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from mini_agent import LLMClient, LaMerAgent
from mini_agent.agent import Agent
from mini_agent.config import Config
from mini_agent.lamer_config import LAMER_SYSTEM_PROMPT_ADDITIONS
from mini_agent.schema import LLMProvider
from mini_agent.tools.base import Tool


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Mini Agent - Minimal single agent with basic tools and MCP support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--workspace",
        help="Workspace directory (default: current directory)",
    )
    parser.add_argument(
        "--lamer",
        action="store_true",
        help="Enable LaMer enhanced capabilities (reflection and meta-learning)",
    )
    return parser.parse_args()


# ... (keep all the existing helper functions from the original CLI)
# I'll import them by copying the relevant parts

async def run_agent(workspace_dir: Path, enable_lamer: bool = False):
    """Run interactive Agent with optional LaMer enhancements."""
    session_start = datetime.now()

    # 1. Load configuration from package directory
    config_path = Config.get_default_config_path()

    if not config_path.exists():
        print(f"{Colors.RED}❌ Configuration file not found{Colors.RESET}")
        print()
        print(f"{Colors.BRIGHT_CYAN}📦 Configuration Search Path:{Colors.RESET}")
        print(f"  {Colors.DIM}1) mini_agent/config/config.yaml{Colors.RESET} (development)")
        print(f"  {Colors.DIM}2) ~/.mini-agent/config/config.yaml{Colors.RESET} (user)")
        print(f"  {Colors.DIM}3) <package>/config/config.yaml{Colors.RESET} (installed)")
        print()
        print(f"{Colors.BRIGHT_YELLOW}🚀 Quick Setup (Recommended):{Colors.RESET}")
        print(f"  {Colors.BRIGHT_GREEN}curl -fsSL https://raw.githubusercontent.com/MiniMax-AI/Mini-Agent/main/scripts/setup-config.sh | bash{Colors.RESET}")
        print()
        print(f"{Colors.DIM}  This will automatically:{Colors.RESET}")
        print(f"{Colors.DIM}    • Create ~/.mini-agent/config/{Colors.RESET}")
        print(f"{Colors.DIM}    • Download configuration files{Colors.RESET}")
        print(f"{Colors.DIM}    • Guide you to add your API Key{Colors.RESET}")
        print()
        print(f"{Colors.BRIGHT_YELLOW}📝 Manual Setup:{Colors.RESET}")
        user_config_dir = Path.home() / ".mini-agent" / "config"
        example_config = Config.get_package_dir() / "config" / "config-example.yaml"
        print(f"  {Colors.DIM}mkdir -p {user_config_dir}{Colors.RESET}")
        print(f"  {Colors.DIM}cp {example_config} {user_config_dir}/config.yaml{Colors.RESET}")
        print(f"  {Colors.DIM}# Then edit {user_config_dir}/config.yaml to add your API Key{Colors.RESET}")
        print()
        return

    try:
        config = Config.from_yaml(config_path)
    except FileNotFoundError:
        print(f"{Colors.RED}❌ Error: Configuration file not found: {config_path}{Colors.RESET}")
        return
    except ValueError as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
        print(f"{Colors.YELLOW}Please check the configuration file format{Colors.RESET}")
        return
    except Exception as e:
        print(f"{Colors.RED}❌ Error: Failed to load configuration file: {e}{Colors.RESET}")
        return

    # 2. Initialize LLM client
    from mini_agent.retry import RetryConfig as RetryConfigBase

    # Convert configuration format
    retry_config = RetryConfigBase(
        enabled=config.llm.retry.enabled,
        max_retries=config.llm.retry.max_retries,
        initial_delay=config.llm.retry.initial_delay,
        max_delay=config.llm.retry.max_delay,
        exponential_base=config.llm.retry.exponential_base,
        retryable_exceptions=(Exception,),
    )

    # Create retry callback function to display retry information in terminal
    def on_retry(exception: Exception, attempt: int):
        """Retry callback function to display retry information"""
        print(f"\n{Colors.BRIGHT_YELLOW}⚠️  LLM call failed (attempt {attempt}): {str(exception)}{Colors.RESET}")
        next_delay = retry_config.calculate_delay(attempt - 1)
        print(f"{Colors.DIM}   Retrying in {next_delay:.1f}s (attempt {attempt + 1})...{Colors.RESET}")

    # Convert provider string to LLMProvider enum
    if config.llm.provider.lower() == "anthropic":
        provider = LLMProvider.ANTHROPIC
    elif config.llm.provider.lower() == "openai":
        provider = LLMProvider.OPENAI
    elif config.llm.provider.lower() == "doubao":
        provider = LLMProvider.DOUBAO
    else:
        raise ValueError(f"Unknown provider: {config.llm.provider}")

    llm_client = LLMClient(
        api_key=config.llm.api_key,
        provider=provider,
        api_base=config.llm.api_base,
        model=config.llm.model,
        retry_config=retry_config if config.llm.retry.enabled else None,
        request_timeout=config.llm.timeout.llm_request,
    )

    # Set retry callback
    if config.llm.retry.enabled:
        llm_client.retry_callback = on_retry
        print(f"{Colors.GREEN}✅ LLM retry mechanism enabled (max {config.llm.retry.max_retries} retries){Colors.RESET}")

    # 3. Initialize base tools (independent of workspace)
    tools, skill_loader = await initialize_base_tools(config)

    # 4. Add workspace-dependent tools
    add_workspace_tools(tools, config, workspace_dir)

    # 5. Load System Prompt (with priority search)
    system_prompt_path = Config.find_config_file(config.agent.system_prompt_path)
    if system_prompt_path and system_prompt_path.exists():
        system_prompt = system_prompt_path.read_text(encoding="utf-8")
        print(f"{Colors.GREEN}✅ Loaded system prompt (from: {system_prompt_path}){Colors.RESET}")
    else:
        system_prompt = "You are Mini-Agent, an intelligent assistant powered by MiniMax M2 that can help users complete various tasks."

    # 6. Inject Skills Metadata into System Prompt (Progressive Disclosure - Level 1)
    if skill_loader:
        skills_metadata = skill_loader.get_skills_metadata_prompt()
        if skills_metadata:
            # Replace placeholder with actual metadata
            system_prompt = system_prompt.replace("{SKILLS_METADATA}", skills_metadata)
            print(f"{Colors.GREEN}✅ Injected {len(skill_loader.loaded_skills)} skills metadata into system prompt{Colors.RESET}")
        else:
            # Remove placeholder if no skills
            system_prompt = system_prompt.replace("{SKILLS_METADATA}", "")
    else:
        # Remove placeholder if skills not enabled
        system_prompt = system_prompt.replace("{SKILLS_METADATA}", "")

    # 7. Add LaMer enhancements if enabled
    if enable_lamer:
        system_prompt += LAMER_SYSTEM_PROMPT_ADDITIONS
        print(f"{Colors.GREEN}✅ LaMer enhanced capabilities enabled (reflection + meta-learning){Colors.RESET}")

    # 8. Create Agent (LaMer or standard)
    if enable_lamer:
        agent = LaMerAgent(
            llm_client=llm_client,
            system_prompt=system_prompt,
            tools=tools,
            max_steps=config.agent.max_steps,
            workspace_dir=str(workspace_dir),
            enable_reflection=True,
            enable_meta_learning=True,
        )
    else:
        agent = Agent(
            llm_client=llm_client,
            system_prompt=system_prompt,
            tools=tools,
            max_steps=config.agent.max_steps,
            workspace_dir=str(workspace_dir),
        )

    # 9. Display welcome information
    print_banner()
    print_session_info(agent, workspace_dir, config.llm.model, config_path)
    if enable_lamer:
        print(f"{Colors.BRIGHT_CYAN}✨ LaMer Mode Active: Reflection and Meta-Learning Enabled{Colors.RESET}")

    # 10. Setup prompt_toolkit session
    # Command completer
    command_completer = WordCompleter(
        ["/help", "/clear", "/history", "/stats", "/exit", "/quit", "/q"],
        ignore_case=True,
        sentence=True,
    )

    # Custom style for prompt
    prompt_style = Style.from_dict(
        {
            "prompt": "#00ff00 bold",  # Green and bold
            "separator": "#666666",  # Gray
        }
    )

    # Custom key bindings
    kb = KeyBindings()

    @kb.add("c-u")  # Ctrl+U: Clear current line
    def _(event):
        """Clear the current input line"""
        event.current_buffer.reset()

    @kb.add("c-l")  # Ctrl+L: Clear screen (optional bonus)
    def _(event):
        """Clear the screen"""
        event.app.renderer.clear()

    @kb.add("c-j")  # Ctrl+J (对应 Ctrl+Enter)
    def _(event):
        """Insert a newline"""
        event.current_buffer.insert_text("\n")

    # Create prompt session with history and auto-suggest
    # Use FileHistory for persistent history across sessions (stored in user's home directory)
    history_file = Path.home() / ".mini-agent" / ".history"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=command_completer,
        style=prompt_style,
        key_bindings=kb,
    )

    # 11. Interactive loop
    while True:
        try:
            # Get user input using prompt_toolkit
            # Use styled list for robust coloring
            user_input = await session.prompt_async(
                [
                    ("class:prompt", "You"),
                    ("", " › "),
                ],
                multiline=False,
                enable_history_search=True,
            )
            user_input = user_input.strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                command = user_input.lower()

                if command in ["/exit", "/quit", "/q"]:
                    print(f"\n{Colors.BRIGHT_YELLOW}👋 Goodbye! Thanks for using Mini Agent{Colors.RESET}\n")
                    print_stats(agent, session_start)
                    break

                elif command == "/help":
                    print_help()
                    continue

                elif command == "/clear":
                    # Clear message history but keep system prompt
                    old_count = len(agent.messages)
                    agent.messages = [agent.messages[0]]  # Keep only system message
                    print(f"{Colors.GREEN}✅ Cleared {old_count - 1} messages, starting new session{Colors.RESET}\n")
                    continue

                elif command == "/history":
                    print(f"\n{Colors.BRIGHT_CYAN}Current session message count: {len(agent.messages)}{Colors.RESET}\n")
                    continue

                elif command == "/stats":
                    print_stats(agent, session_start)
                    continue

                else:
                    print(f"{Colors.RED}❌ Unknown command: {user_input}{Colors.RESET}")
                    print(f"{Colors.DIM}Type /help to see available commands{Colors.RESET}\n")
                    continue

            # Normal conversation - exit check
            if user_input.lower() in ["exit", "quit", "q"]:
                print(f"\n{Colors.BRIGHT_YELLOW}👋 Goodbye! Thanks for using Mini Agent{Colors.RESET}\n")
                print_stats(agent, session_start)
                break

            # Run Agent
            print(f"\n{Colors.BRIGHT_BLUE}Agent{Colors.RESET} {Colors.DIM}›{Colors.RESET} {Colors.DIM}Thinking...{Colors.RESET}\n")
            agent.add_user_message(user_input)
            _ = await agent.run()

            # Visual separation - keep it simple like the reference code
            print(f"\n{Colors.DIM}{'─' * 60}{Colors.RESET}\n")

        except KeyboardInterrupt:
            print(f"\n\n{Colors.BRIGHT_YELLOW}👋 Interrupt signal detected, exiting...{Colors.RESET}\n")
            print_stats(agent, session_start)
            break

        except Exception as e:
            print(f"\n{Colors.RED}❌ Error: {e}{Colors.RESET}")
            print(f"{Colors.DIM}{'─' * 60}{Colors.RESET}\n")

    # 12. Cleanup MCP connections
    try:
        print(f"{Colors.BRIGHT_CYAN}Cleaning up MCP connections...{Colors.RESET}")
        await cleanup_mcp_connections()
        print(f"{Colors.GREEN}✅ Cleanup complete{Colors.RESET}\n")
    except asyncio.CancelledError:
        # Task was cancelled (e.g., Ctrl+C, timeout), cleanup what we can
        print(f"{Colors.YELLOW}⚠️  Interrupted during cleanup{Colors.RESET}\n")
    except Exception as e:
        print(f"{Colors.YELLOW}Error during cleanup (can be ignored): {e}{Colors.RESET}\n")


def main():
    """Main entry point for CLI"""
    # Parse command line arguments
    args = parse_args()

    # Determine workspace directory
    if args.workspace:
        workspace_dir = Path(args.workspace).absolute()
    else:
        # Use current working directory
        workspace_dir = Path.cwd()

    # Ensure workspace directory exists
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Run the agent (config always loaded from package directory)
    try:
        asyncio.run(run_agent(workspace_dir, enable_lamer=args.lamer))
    except KeyboardInterrupt:
        # Ctrl+C or SIGINT was sent - normal exit
        print(f"\n{Colors.BRIGHT_CYAN}Shutdown complete.{Colors.RESET}")
    except asyncio.CancelledError:
        # Task was cancelled - treat as normal shutdown, not an error
        print(f"\n{Colors.BRIGHT_CYAN}Shutdown complete.{Colors.RESET}")


if __name__ == "__main__":
    main()

# Import all the helper functions from the original CLI
# This is a simplified approach - in practice, we'd refactor to avoid duplication
from mini_agent.cli import (
    Colors, initialize_base_tools, add_workspace_tools, print_banner, 
    print_session_info, print_help, print_stats, cleanup_mcp_connections
)