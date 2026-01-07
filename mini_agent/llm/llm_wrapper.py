"""LLM client wrapper that supports multiple providers.

This module provides a unified interface for different LLM providers
(Anthropic and OpenAI) through a single LLMClient class.
"""

import logging

from ..retry import RetryConfig
from ..schema import LLMProvider, LLMResponse, Message
from .anthropic_client import AnthropicClient
from .base import LLMClientBase
from .doubao_client import DoubaoClient
from .openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM Client wrapper supporting multiple providers.

    This class provides a unified interface for different LLM providers.
    It automatically instantiates the correct underlying client based on
    the provider parameter and appends the appropriate API endpoint suffix.

    Supported providers:
    - anthropic: Appends /anthropic to api_base
    - openai: Appends /v1 to api_base
    - doubao: Uses Volcano Engine's OpenAI-compatible endpoint (no suffix added)

    For MiniMax API (api.minimax.io or api.minimaxi.com), special handling ensures
    correct suffixes are applied based on provider.
    For third-party APIs (e.g., https://api.siliconflow.cn/v1), api_base is used as-is.
    """

    # MiniMax API domains that need automatic suffix handling
    MINIMAX_DOMAINS = ("api.minimax.io", "api.minimaxi.com")

    def __init__(
        self,
        api_key: str,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        api_base: str = "https://api.minimaxi.com",
        model: str = "MiniMax-M2.1",
        retry_config: RetryConfig | None = None,
        request_timeout: float = 60.0,
    ):
        """Initialize LLM client with specified provider.

        Args:
            api_key: API key for authentication
            provider: LLM provider (anthropic, openai, or doubao)
            api_base: Base URL for the API (default: https://api.minimaxi.com)
                     - For anthropic/openai: Will be suffixed with /anthropic or /v1
                     - For doubao: Use Volcano Engine endpoint (default: https://ark.cn-beijing.volces.com/api/v3)
                     For MiniMax API, suffix is auto-appended based on provider.
                     For third-party APIs (e.g., https://api.siliconflow.cn/v1), used as-is.
            model: Model name to use
            retry_config: Optional retry configuration
            request_timeout: Timeout for API requests in seconds
        """
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.retry_config = retry_config or RetryConfig()
        self.request_timeout = request_timeout

        # Normalize api_base (remove trailing slash) and strip existing suffixes if present
        api_base = api_base.rstrip("/")

        # Special handling for doubao (no suffix added)
        if provider == LLMProvider.DOUBAO:
            full_api_base = api_base.rstrip('/')
        else:
            # For anthropic/openai, check if this is a MiniMax API endpoint
            is_minimax = any(domain in api_base for domain in self.MINIMAX_DOMAINS)

            if is_minimax:
                # For MiniMax API, ensure correct suffix based on provider
                # Strip any existing suffix first
                base_without_suffix = api_base.replace("/anthropic", "").replace("/v1", "")
                if provider == LLMProvider.ANTHROPIC:
                    full_api_base = f"{base_without_suffix}/anthropic"
                elif provider == LLMProvider.OPENAI:
                    full_api_base = f"{base_without_suffix}/v1"
                else:
                    raise ValueError(f"Unsupported provider: {provider}")
            else:
                # For third-party APIs, append provider-specific suffix
                if provider == LLMProvider.ANTHROPIC:
                    full_api_base = f"{api_base}/anthropic"
                elif provider == LLMProvider.OPENAI:
                    full_api_base = f"{api_base}/v1"
                else:
                    raise ValueError(f"Unsupported provider: {provider}")

        self.api_base = full_api_base

        # Instantiate the appropriate client
        self._client: LLMClientBase
        if provider == LLMProvider.ANTHROPIC:
            self._client = AnthropicClient(
                api_key=api_key,
                api_base=full_api_base,
                model=model,
                retry_config=retry_config,
                request_timeout=request_timeout,
            )
        elif provider == LLMProvider.OPENAI:
            self._client = OpenAIClient(
                api_key=api_key,
                api_base=full_api_base,
                model=model,
                retry_config=retry_config,
                request_timeout=request_timeout,
            )
        elif provider == LLMProvider.DOUBAO:
            self._client = DoubaoClient(
                api_key=api_key,
                api_base=full_api_base,
                model=model,
                retry_config=retry_config,
                request_timeout=request_timeout,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        logger.info("Initialized LLM client with provider: %s, api_base: %s", provider, full_api_base)

    @property
    def retry_callback(self):
        """Get retry callback."""
        return self._client.retry_callback

    @retry_callback.setter
    def retry_callback(self, value):
        """Set retry callback."""
        self._client.retry_callback = value

    async def generate(
        self,
        messages: list[Message],
        tools: list | None = None,
    ) -> LLMResponse:
        """Generate response from LLM.

        Args:
            messages: List of conversation messages
            tools: Optional list of Tool objects or dicts

        Returns:
            LLMResponse containing the generated content
        """
        return await self._client.generate(messages, tools)
