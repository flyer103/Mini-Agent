"""Base router class for LLM Proxy.

Defines the interface that all routing strategies must implement.
"""

from abc import ABC, abstractmethod


class BaseRouter(ABC):
    """Abstract base class for all routing strategies.

    Routers determine the order in which providers should be tried
    for LLM requests, implementing different load balancing and failover strategies.
    """

    @abstractmethod
    def get_providers(self) -> list[str]:
        """Get ordered list of provider names to try.

        Returns:
            List of provider names in the order they should be attempted
        """
        pass

    @abstractmethod
    def on_success(self, provider_name: str) -> None:
        """Notify router of a successful request.

        Args:
            provider_name: Name of the provider that succeeded
        """
        pass

    @abstractmethod
    def on_failure(self, provider_name: str) -> None:
        """Notify router of a failed request.

        Args:
            provider_name: Name of the provider that failed
        """
        pass
