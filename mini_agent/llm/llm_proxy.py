"""LLM Proxy client with multi-provider support and failover.

This module provides LLMProxyClient, which manages multiple LLM providers,
implementing routing strategies and automatic failover for high availability.
"""

import asyncio
import logging
from typing import Any, AsyncIterator

from ..retry import RetryConfig
from ..schema import LLMResponse, Message
from ..schema.llm_proxy import LLMProxyConfig, ProviderStatus
from .anthropic_client import AnthropicClient
from .doubao_client import DoubaoClient
from .openai_client import OpenAIClient
from .provider_health import ProviderHealthChecker
from .router import BaseRouter, FailoverRouter, PriorityRouter, RoundRobinRouter, WeightedRouter

logger = logging.getLogger(__name__)


class LLMProxyClient:
    """LLM Proxy client supporting multiple providers with automatic failover.

    This client manages multiple LLM providers, routing requests according to
    configured strategies and automatically failing over when providers fail.

    Attributes:
        config: LLM Proxy configuration
        providers: Dictionary of provider configurations and health checkers
        router: Routing strategy implementation
        health_check_task: Background health check task (if enabled)
    """

    def __init__(
        self,
        config: LLMProxyConfig,
        retry_config: RetryConfig | None = None,
        request_timeout: float = 60.0,
    ):
        """Initialize LLM Proxy Client.

        Args:
            config: LLM Proxy configuration
            retry_config: Retry configuration
            request_timeout: Request timeout in seconds
        """
        self.config = config
        self.retry_config = retry_config or RetryConfig()
        self.request_timeout = request_timeout
        self._monitor = None

        # Initialize all providers
        self.providers: dict[str, dict[str, Any]] = {}
        for provider_cfg in config.providers:
            self._initialize_provider(provider_cfg)

        if not self.providers:
            raise ValueError("No providers configured for LLM Proxy")

        # Create router for the configured strategy
        self.router = self._create_router(config.strategy)

        # Start health check task if enabled
        self.health_check_task: asyncio.Task | None = None
        if config.health_check_interval > 0:
            self.start_health_check()

        logger.info(
            "LLM Proxy initialized with %d providers, strategy: %s",
            len(self.providers),
            config.strategy,
        )

    def _initialize_provider(self, provider_cfg: Any) -> None:
        """Initialize a single provider.

        Args:
            provider_cfg: Provider configuration
        """
        provider_info = {
            "config": provider_cfg,
            "health_checker": ProviderHealthChecker(
                provider_name=provider_cfg.name,
                max_failures=provider_cfg.max_failures,
                failure_window=provider_cfg.failure_window,
                recovery_timeout=provider_cfg.recovery_timeout,
            ),
            "last_used": 0,  # Last usage timestamp (for round-robin)
        }
        self.providers[provider_cfg.name] = provider_info

    def _create_router(self, strategy: Any) -> BaseRouter:
        """Create router instance for the specified strategy.

        Args:
            strategy: Routing strategy enum value

        Returns:
            Router instance
        """
        if strategy.value == "failover":
            return FailoverRouter(self.providers)
        elif strategy.value == "round_robin":
            return RoundRobinRouter(self.providers)
        elif strategy.value == "priority":
            return PriorityRouter(self.providers)
        elif strategy.value == "weighted":
            return WeightedRouter(self.providers)
        else:
            raise ValueError(f"Unsupported routing strategy: {strategy}")

    async def generate(self, messages: list[Message], tools: list | None = None) -> LLMResponse:
        """Generate response using proxy with automatic failover.

        Attempts to generate a response by trying providers in the order
        determined by the routing strategy. If a provider fails, the next
        provider is tried automatically.

        Args:
            messages: List of conversation messages
            tools: Optional list of available tools

        Returns:
            LLMResponse from the first successful provider

        Raises:
            Exception: If all providers fail
        """
        last_exception = None
        attempted_providers = []

        # Try providers in the order specified by the router
        for provider_name in self.router.get_providers():
            # Check if provider is available
            if not self._is_provider_available(provider_name):
                continue

            attempted_providers.append(provider_name)
            provider_info = self.providers[provider_name]
            provider_cfg = provider_info["config"]

            try:
                logger.debug("Attempting request to provider: %s", provider_name)

                # Create client for this provider
                client = self._create_client(provider_cfg)

                # Generate response
                response = await client.generate(messages, tools)

                # Record success
                provider_info["health_checker"].record_success()
                self.router.on_success(provider_name)

                logger.info(
                    "Request succeeded with provider: %s (tried: %s)",
                    provider_name,
                    attempted_providers,
                )

                return response

            except Exception as e:
                # Record failure
                should_mark_unhealthy = provider_info["health_checker"].record_failure()
                last_exception = e

                logger.warning(
                    "Provider %s failed: %s (unhealthy: %s, tried: %s)",
                    provider_name,
                    str(e)[:200],  # Log first 200 chars
                    should_mark_unhealthy,
                    attempted_providers,
                )

                self.router.on_failure(provider_name)

                # Try next provider
                continue

        # All providers failed
        error_msg = f"All {len(attempted_providers)} providers failed. Last error: {last_exception}"
        logger.error(error_msg)
        raise Exception(error_msg)

    async def generate_stream(self, messages: list[Message], tools: list | None = None) -> AsyncIterator[LLMResponse]:
        """Generate streaming response using proxy with automatic failover.

        Attempts to generate a streaming response by trying providers in the order
        determined by the routing strategy. If a provider fails, the next
        provider is tried automatically.

        Args:
            messages: List of conversation messages
            tools: Optional list of available tools

        Yields:
            LLMResponse chunks from the first successful provider

        Raises:
            Exception: If all providers fail
        """
        last_exception = None
        attempted_providers = []

        # Try providers in the order specified by the router
        for provider_name in self.router.get_providers():
            # Check if provider is available
            if not self._is_provider_available(provider_name):
                continue

            attempted_providers.append(provider_name)
            provider_info = self.providers[provider_name]
            provider_cfg = provider_info["config"]

            try:
                logger.debug("Attempting streaming request to provider: %s", provider_name)

                # Create client for this provider
                client = self._create_client(provider_cfg)

                # Generate streaming response
                async for chunk in client.generate_stream(messages, tools):
                    # Record success
                    provider_info["health_checker"].record_success()
                    self.router.on_success(provider_name)

                    logger.info(
                        "Streaming request succeeded with provider: %s (tried: %s)",
                        provider_name,
                        attempted_providers,
                    )

                    yield chunk

            except Exception as e:
                # Record failure
                should_mark_unhealthy = provider_info["health_checker"].record_failure()
                last_exception = e

                logger.warning(
                    "Provider %s failed during streaming: %s (unhealthy: %s, tried: %s)",
                    provider_name,
                    str(e)[:200],  # Log first 200 chars
                    should_mark_unhealthy,
                    attempted_providers,
                )

                self.router.on_failure(provider_name)

                # Try next provider
                continue

        # All providers failed
        error_msg = f"All {len(attempted_providers)} providers failed during streaming. Last error: {last_exception}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _create_client(self, provider_cfg: Any) -> Any:
        """Create a client instance for the specified provider.

        Args:
            provider_cfg: Provider configuration

        Returns:
            Client instance for the provider
        """
        provider_type = provider_cfg.provider.lower()

        if provider_type == "anthropic":
            return AnthropicClient(
                api_key=provider_cfg.api_key,
                api_base=provider_cfg.api_base,
                model=provider_cfg.model,
                retry_config=self.retry_config,
                request_timeout=self.request_timeout,
            )
        elif provider_type == "openai":
            return OpenAIClient(
                api_key=provider_cfg.api_key,
                api_base=provider_cfg.api_base,
                model=provider_cfg.model,
                retry_config=self.retry_config,
                request_timeout=self.request_timeout,
            )
        elif provider_type == "doubao":
            return DoubaoClient(
                api_key=provider_cfg.api_key,
                api_base=provider_cfg.api_base,
                model=provider_cfg.model,
                retry_config=self.retry_config,
                request_timeout=self.request_timeout,
            )
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

    def _is_provider_available(self, provider_name: str) -> bool:
        """Check if a provider is available for requests.

        A provider is available if it's enabled and either healthy or ready
        for a recovery attempt.

        Args:
            provider_name: Name of the provider to check

        Returns:
            True if provider is available, False otherwise
        """
        provider_info = self.providers[provider_name]
        provider_cfg = provider_info["config"]
        health_checker = provider_info["health_checker"]

        # Check if manually disabled
        if not provider_cfg.enabled:
            logger.debug("Provider %s is disabled", provider_name)
            return False

        # Check health status
        if health_checker.status == ProviderStatus.HEALTHY:
            return True

        # If unhealthy, check if we should attempt recovery
        if health_checker.should_attempt_recovery():
            logger.info("Attempting recovery for provider: %s", provider_name)
            return True

        logger.debug("Provider %s is unhealthy and not ready for recovery", provider_name)
        return False

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on all providers.

        Returns:
            Dictionary with health status for each provider
        """
        results = {}

        for provider_name, provider_info in self.providers.items():
            provider_cfg = provider_info["config"]

            if not provider_cfg.enabled:
                results[provider_name] = {"status": "disabled", "healthy": False}
                continue

            health_checker = provider_info["health_checker"]

            # Simple health check: check if we should attempt recovery
            if health_checker.status == ProviderStatus.HEALTHY:
                results[provider_name] = {"status": "healthy", "healthy": True}
            elif health_checker.should_attempt_recovery():
                results[provider_name] = {"status": "recovering", "healthy": True}
            else:
                results[provider_name] = {"status": "unhealthy", "healthy": False}

        return results

    def start_health_check(self) -> None:
        """Start background health checking task.

        Creates a background task that periodically checks provider health.
        Only starts if an event loop is running.
        """
        import sys
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running event loop, cannot start health check task. Call start_health_check() within an async context.")
            return

        async def health_check_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.health_check_interval)
                    await self._perform_health_check()
                except asyncio.CancelledError:
                    logger.debug("Health check task cancelled")
                    break
                except Exception as e:
                    logger.error("Error in health check loop: %s", e)

        self.health_check_task = asyncio.create_task(health_check_loop())
        logger.info("Started health check task with interval %d seconds", self.config.health_check_interval)

    async def _perform_health_check(self) -> None:
        """Execute health check cycle.

        Currently, health is determined by recent failure history.
        Future enhancements could include actual API health checks.
        """
        logger.debug("Performing health check cycle")

        # The current implementation uses passive health checking based on
        # request failure history. This method is a placeholder for active
        # health checks in the future.

        # Log current health status
        health_status = await self.health_check()
        for provider_name, status in health_status.items():
            logger.debug("Provider %s health: %s", provider_name, status["status"])

    def stop_health_check(self) -> None:
        """Stop background health checking task."""
        if self.health_check_task and not self.health_check_task.done():
            self.health_check_task.cancel()
            logger.info("Stopped health check task")

    def get_stats(self) -> dict[str, Any]:
        """Get proxy statistics.

        Returns:
            Dictionary with statistics about provider health and usage
        """
        stats = {"total_providers": len(self.providers), "providers": {}}

        for provider_name, provider_info in self.providers.items():
            provider_cfg = provider_info["config"]
            health_checker = provider_info["health_checker"]

            stats["providers"][provider_name] = {
                "enabled": provider_cfg.enabled,
                "status": health_checker.status.value,
                "provider_type": provider_cfg.provider,
                "priority": provider_cfg.priority,
                "weight": provider_cfg.weight,
                "recent_failures": len(health_checker.failure_times),
            }

        return stats

    def __del__(self):
        """Cleanup when instance is destroyed."""
        if self.health_check_task and not self.health_check_task.done():
            self.health_check_task.cancel()
