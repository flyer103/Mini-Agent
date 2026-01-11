"""Failover router implementation.

Provides primary-backup failover routing strategy, where providers
are tried in strict priority order until one succeeds.
"""

from .base import BaseRouter


class FailoverRouter(BaseRouter):
    """Primary-backup failover router.

    Routes requests to providers in strict priority order (lower priority number
    = higher priority). If the primary provider fails, the next provider is tried,
    and so on until a provider succeeds or all providers fail.

    This is ideal for scenarios where you have a preferred provider but want
    automatic failover to backup providers.
    """

    def __init__(self, providers: dict[str, dict]):
        """Initialize the failover router.

        Args:
            providers: Dictionary of provider information
                       Format: {name: {"config": ProviderConfig, ...}}
        """
        self.providers = providers
        # Sort providers by priority (lower number = higher priority)
        self.sorted_providers = sorted(
            providers.keys(),
            key=lambda x: providers[x]["config"].priority
        )

    def get_providers(self) -> list[str]:
        """Get providers in priority order.

        Returns:
            List of provider names sorted by priority (highest priority first)
        """
        return self.sorted_providers.copy()  # Return copy to prevent external modification

    def on_success(self, provider_name: str) -> None:
        """Record successful request.

        In failover mode, priority order is maintained regardless of success/failure.

        Args:
            provider_name: Name of the successful provider
        """
        # Priority order remains unchanged in failover mode
        pass

    def on_failure(self, provider_name: str) -> None:
        """Record failed request.

        In failover mode, priority order is maintained regardless of success/failure.

        Args:
            provider_name: Name of the failed provider
        """
        # Priority order remains unchanged in failover mode
        pass
