"""Weighted router implementation.

Provides weighted load balancing strategy, distributing requests
across providers based on configured weights.
"""

import random
from collections import defaultdict

from .base import BaseRouter


class WeightedRouter(BaseRouter):
    """Weighted load balancing router.

    Routes requests to providers based on configured weights, with higher-weight
    providers receiving proportionally more requests. Weights remain fixed but
    future enhancements could support dynamic weight adjustment.

    This is ideal for scenarios where providers have different capacities or costs,
    and you want to distribute load proportionally.
    """

    def __init__(self, providers: dict[str, dict]):
        """Initialize the weighted router.

        Args:
            providers: Dictionary of provider information
                       Format: {name: {"config": ProviderConfig, ...}}
        """
        self.providers = providers
        # Cache weights and update when providers change
        self._update_weights()

    def _update_weights(self) -> None:
        """Update the list of enabled providers and their weights."""
        self.enabled_providers = [
            (name, info["config"].weight)
            for name, info in self.providers.items()
            if info["config"].enabled
        ]
        self.total_weight = sum(weight for _, weight in self.enabled_providers)

    def get_providers(self) -> list[str]:
        """Get providers in weighted random order.

        Returns a list of provider names where higher-weight providers appear
        earlier (on average), but all providers are included to ensure failover.

        Returns:
            List of provider names ordered by weighted random selection,
            followed by any providers not selected
        """
        # Update weights (in case providers were enabled/disabled or weights changed)
        self._update_weights()

        if not self.enabled_providers or self.total_weight == 0:
            return []

        providers = [name for name, _ in self.enabled_providers]
        weights = [weight for _, weight in self.enabled_providers]

        # Use weighted random selection to prioritize high-weight providers
        # Select k=len(providers) to create a weighted ordering
        weighted_random = random.choices(providers, weights=weights, k=len(providers))

        # Deduplicate while preserving weighted order
        seen = set()
        result = []
        for provider in weighted_random:
            if provider not in seen:
                seen.add(provider)
                result.append(provider)

        # Append any providers that weren't randomly selected (for failover)
        for provider in providers:
            if provider not in seen:
                result.append(provider)

        return result

    def on_success(self, provider_name: str) -> None:
        """Record successful request.

        In weighted mode, weights remain fixed regardless of success/failure.
        Future enhancements could adjust weights based on performance or cost.

        Args:
            provider_name: Name of the successful provider
        """
        # Weights remain unchanged in basic weighted mode
        pass

    def on_failure(self, provider_name: str) -> None:
        """Record failed request.

        In weighted mode, weights remain fixed regardless of success/failure.
        Future enhancements could adjust weights based on performance.

        Args:
            provider_name: Name of the failed provider
        """
        # Weights remain unchanged in basic weighted mode
        pass
