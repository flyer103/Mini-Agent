"""Priority router implementation.

Provides priority-based routing strategy, similar to failover but with
potential for dynamic priority adjustments.
"""

from .base import BaseRouter


class PriorityRouter(BaseRouter):
    """Priority-based routing router.

    Routes requests to providers in priority order (lower number = higher priority).
    Unlike failover, this router may support dynamic priority adjustments based
    on performance metrics.

    This is ideal for scenarios where you want to prefer certain providers
    but can tolerate using lower-priority providers when necessary.
    """

    def __init__(self, providers: dict[str, dict]):
        """Initialize the priority router.

        Args:
            providers: Dictionary of provider information
                       Format: {name: {"config": ProviderConfig, ...}}
        """
        self.providers = providers
        # Cache list of enabled providers sorted by priority
        self._update_sorted_providers()

    def _update_sorted_providers(self) -> None:
        """Update the list of enabled providers sorted by priority."""
        self.sorted_providers = sorted(
            [name for name, info in self.providers.items() if info["config"].enabled],
            key=lambda x: self.providers[x]["config"].priority,
        )

    def get_providers(self) -> list[str]:
        """Get providers in priority order.

        Returns:
            List of provider names sorted by priority (highest priority first)
        """
        # Update sorted providers (in case providers were enabled/disabled)
        self._update_sorted_providers()
        return self.sorted_providers.copy()

    def on_success(self, provider_name: str) -> None:
        """Record successful request.

        In basic priority mode, priorities remain fixed regardless of success/failure.
        Future enhancements could adjust priorities based on performance.

        Args:
            provider_name: Name of the successful provider
        """
        # Priority order remains unchanged in basic priority mode
        pass

    def on_failure(self, provider_name: str) -> None:
        """Record failed request.

        In basic priority mode, priorities remain fixed regardless of success/failure.
        Future enhancements could adjust priorities based on performance.

        Args:
            provider_name: Name of the failed provider
        """
        # Priority order remains unchanged in basic priority mode
        pass
