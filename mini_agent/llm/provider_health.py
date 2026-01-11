"""Provider health monitoring and failure detection.

This module provides health checking capabilities for LLM providers,
tracking failures and success rates to determine provider availability.
"""

import time

from ..schema.llm_proxy import ProviderStatus


class ProviderHealthChecker:
    """Health checker for LLM providers.

    Monitors provider health by tracking request successes and failures,
    marking providers as unhealthy when failure thresholds are exceeded,
    and controlling recovery attempts.

    Attributes:
        provider_name: Unique identifier for the provider
        max_failures: Maximum consecutive failures before marking as unhealthy
        failure_window: Time window (seconds) for tracking failures
        recovery_timeout: Minimum time (seconds) before attempting recovery
        failure_times: List of timestamps of recent failures
        status: Current health status of the provider
        last_failure_time: Timestamp of the most recent failure
    """

    def __init__(
        self,
        provider_name: str,
        max_failures: int,
        failure_window: int,
        recovery_timeout: int,
    ):
        """Initialize the health checker.

        Args:
            provider_name: Unique identifier for the provider
            max_failures: Maximum consecutive failures before marking as unhealthy
            failure_window: Time window (seconds) for tracking failures
            recovery_timeout: Minimum time (seconds) before attempting recovery
        """
        self.provider_name = provider_name
        self.max_failures = max_failures
        self.failure_window = failure_window
        self.recovery_timeout = recovery_timeout
        self.failure_times: list[float] = []
        self.status = ProviderStatus.HEALTHY
        self.last_failure_time: float | None = None

    def record_success(self) -> None:
        """Record a successful request.

        Clears the failure history and marks the provider as healthy.
        """
        self.failure_times.clear()
        self.status = ProviderStatus.HEALTHY
        self.last_failure_time = None

    def record_failure(self) -> bool:
        """Record a failed request and check if threshold is exceeded.

        Adds the current timestamp to the failure list, cleans up expired
        failures, and checks if the number of failures exceeds the threshold.

        Returns:
            True if the provider should be marked as unhealthy, False otherwise
        """
        current_time = time.time()
        self.failure_times.append(current_time)
        self.last_failure_time = current_time

        # Clean up expired failure records
        cutoff_time = current_time - self.failure_window
        self.failure_times = [t for t in self.failure_times if t > cutoff_time]

        # Check if max failures exceeded
        if len(self.failure_times) >= self.max_failures:
            self.status = ProviderStatus.UNHEALTHY
            return True
        return False

    def should_attempt_recovery(self) -> bool:
        """Determine if recovery should be attempted.

        Checks if enough time has passed since the last failure to attempt
        recovery. Only applicable for providers marked as unhealthy.

        Returns:
            True if recovery should be attempted, False otherwise
        """
        if self.status != ProviderStatus.UNHEALTHY:
            return False
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
