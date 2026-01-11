"""LLM client wrapper that supports multiple providers.

This module provides a unified interface for different LLM providers
(Anthropic and OpenAI) through a single LLMClient class.
"""

import logging
from typing import Any, AsyncIterator

from ..retry import RetryConfig
from ..schema import LLMProvider, LLMResponse, Message
from .anthropic_client import AnthropicClient
from .base import LLMClientBase
from .doubao_client import DoubaoClient
from .llm_proxy import LLMProxyClient
from .openai_client import OpenAIClient

try:
    from ..schema.llm_proxy import LLMProxyConfig
except ImportError:
    LLMProxyConfig = Any

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
        proxy_config: "LLMProxyConfig | None" = None,  # type: ignore
    ):
        """Initialize LLM client with specified provider or proxy mode.

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
            proxy_config: Optional LLM Proxy configuration for multi-provider mode
        """
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.retry_config = retry_config or RetryConfig()
        self.request_timeout = request_timeout
        self.proxy_config = proxy_config

        # Store raw api_base for normalization
        self._api_base_raw = api_base

        # Determine connection mode
        if proxy_config and getattr(proxy_config, "enabled", False):
            self._mode = "proxy"
            self._init_proxy_mode()
        else:
            self._mode = "single"
            self._init_single_mode()

    def _init_single_mode(self) -> None:
        """Initialize single provider mode."""
        logger.info("Initializing single provider mode: %s", self.provider)

        # Normalize api_base
        api_base = self._get_normalized_api_base()
        self.api_base = api_base

        self._client = self._create_single_provider_client(
            self.provider, self.api_key, api_base, self.model, self.retry_config, self.request_timeout
        )

    def _init_proxy_mode(self) -> None:
        """Initialize proxy mode."""
        logger.info("Initializing LLM Proxy mode with strategy: %s", self.proxy_config.strategy)
        self._client = LLMProxyClient(
            config=self.proxy_config,
            retry_config=self.retry_config,
            request_timeout=self.request_timeout,
        )

    def _get_normalized_api_base(self) -> str:
        """Normalize API base URL and apply provider-specific suffixes."""
        api_base = self._api_base_raw.rstrip("/")

        # Special handling for doubao (no suffix added)
        if self.provider == LLMProvider.DOUBAO:
            full_api_base = api_base.rstrip('/')
        else:
            # For anthropic/openai, check if this is a MiniMax API endpoint
            is_minimax = any(domain in api_base for domain in self.MINIMAX_DOMAINS)

            if is_minimax:
                # For MiniMax API, ensure correct suffix based on provider
                # Strip any existing suffix first
                base_without_suffix = api_base.replace("/anthropic", "").replace("/v1", "")
                if self.provider == LLMProvider.ANTHROPIC:
                    full_api_base = f"{base_without_suffix}/anthropic"
                elif self.provider == LLMProvider.OPENAI:
                    full_api_base = f"{base_without_suffix}/v1"
                else:
                    raise ValueError(f"Unsupported provider: {self.provider}")
            else:
                # For third-party APIs, append provider-specific suffix
                if self.provider == LLMProvider.ANTHROPIC:
                    full_api_base = f"{api_base}/anthropic"
                elif self.provider == LLMProvider.OPENAI:
                    full_api_base = f"{api_base}/v1"
                else:
                    raise ValueError(f"Unsupported provider: {self.provider}")

        return full_api_base

    def _create_single_provider_client(
        self,
        provider: LLMProvider,
        api_key: str,
        api_base: str,
        model: str,
        retry_config: RetryConfig | None,
        request_timeout: float,
    ) -> LLMClientBase:
        """Create a single provider client instance.

        Args:
            provider: LLM provider type
            api_key: API key
            api_base: API base URL
            model: Model name
            retry_config: Retry configuration
            request_timeout: Request timeout

        Returns:
            Client instance for the provider
        """
        if provider == LLMProvider.ANTHROPIC:
            return AnthropicClient(
                api_key=api_key,
                api_base=api_base,
                model=model,
                retry_config=retry_config,
                request_timeout=request_timeout,
            )
        elif provider == LLMProvider.OPENAI:
            return OpenAIClient(
                api_key=api_key,
                api_base=api_base,
                model=model,
                retry_config=retry_config,
                request_timeout=request_timeout,
            )
        elif provider == LLMProvider.DOUBAO:
            return DoubaoClient(
                api_key=api_key,
                api_base=api_base,
                model=model,
                retry_config=retry_config,
                request_timeout=request_timeout,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @property
    def retry_callback(self):
        """Get retry callback."""
        return self._client.retry_callback

    @retry_callback.setter
    def retry_callback(self, value):
        """Set retry callback."""
        self._client.retry_callback = value

    @property
    def is_proxy_mode(self) -> bool:
        """Check if client is in proxy mode.

        Returns:
            True if in proxy mode, False if in single provider mode
        """
        return self._mode == "proxy"

    @property
    def is_single_mode(self) -> bool:
        """Check if client is in single provider mode.

        Returns:
            True if in single provider mode, False if in proxy mode
        """
        return self._mode == "single"

    async def generate(
        self,
        messages: list[Message],
        tools: list | None = None,
    ) -> LLMResponse:
        """Generate response from LLM.

        In single provider mode, uses the configured provider.
        In proxy mode, routes request according to the proxy configuration.

        Args:
            messages: List of conversation messages
            tools: Optional list of Tool objects or dicts

        Returns:
            LLMResponse containing the generated content
        """
        return await self._client.generate(messages, tools)

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list | None = None,
    ) -> AsyncIterator[LLMResponse]:
        """Generate streaming response from LLM.

        In single provider mode, uses the configured provider.
        In proxy mode, routes request according to the proxy configuration.

        Args:
            messages: List of conversation messages
            tools: Optional list of Tool objects or dicts

        Yields:
            LLMResponse chunks as they become available
        """
        async for chunk in self._client.generate_stream(messages, tools):
            yield chunk
