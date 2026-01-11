"""Round-robin router implementation.

Provides round-robin load balancing strategy, cycling through providers
in a circular order to distribute load evenly.
"""

from .base import BaseRouter


class RoundRobinRouter(BaseRouter):
    """Round-robin load balancing router.

    Routes requests to providers in a circular order, distributing load
    evenly across all available providers. Failed providers are automatically
    skipped when they become unhealthy.

    This is ideal for scenarios where you want to distribute load evenly
    across multiple equally-capable providers.
    """

    def __init__(self, providers: dict[str, dict]):
        """Initialize the round-robin router.

        Args:
            providers: Dictionary of provider information
                       Format: {name: {"config": ProviderConfig, ...}}
        """
        self.providers = providers
        self.current_index = 0
        # Cache list of enabled providers
        self._update_enabled_providers()

    def _update_enabled_providers(self) -> None:
        """Update the list of enabled providers."""
        self.enabled_providers = [
            name for name, info in self.providers.items() if info["config"].enabled
        ]

    def get_providers(self) -> list[str]:
        """Get providers in round-robin order.

        Returns:
            List of provider names starting from the current index,
            cycling through all enabled providers
        """
        # Update enabled providers list (in case providers were enabled/disabled)
        self._update_enabled_providers()

        if not self.enabled_providers:
            return []

        # Start from current index and cycle through all providers
        return (
            self.enabled_providers[self.current_index :]
            + self.enabled_providers[: self.current_index]
        )

    def on_success(self, provider_name: str) -> None:
        """Record successful request and advance to next provider.

        After a successful request, the next provider in the cycle
        will be used for the subsequent request.

        Args:
            provider_name: Name of the successful provider
        """
        if not self.enabled_providers:
            return

        try:
            # Find the index of the successful provider
            current_idx = self.enabled_providers.index(provider_name)
            # Advance to next provider (wrap around if at end)
            self.current_index = (current_idx + 1) % len(self.enabled_providers)
        except ValueError:
            # Provider not in enabled list, ignore
            pass

    def on_failure(self, provider_name: str) -> None:
        """Record failed request.

        In round-robin mode, the current index remains unchanged when
        a provider fails, but the failed provider will be skipped in
        subsequent get_providers() calls if it becomes unhealthy.

        Args:
            provider_name: Name of the failed provider
        """
        # Current index stays the same, failed provider will be skipped by health checker
        pass
