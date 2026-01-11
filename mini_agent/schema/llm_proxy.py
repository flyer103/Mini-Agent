"""LLM Proxy data structures and configurations.

This module defines the configuration models for LLM Proxy, including
provider configurations, routing strategies, and health check settings.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ProxyStrategy(str, Enum):
    """LLM Proxy routing strategies.

    Supported strategies:
    - FAILOVER: Primary-backup failover mode
    - ROUND_ROBIN: Round-robin load balancing
    - PRIORITY: Priority-based routing
    - WEIGHTED: Weighted load balancing
    """

    FAILOVER = "failover"  # 主备故障转移
    ROUND_ROBIN = "round_robin"  # 轮询
    PRIORITY = "priority"  # 优先级
    WEIGHTED = "weighted"  # 权重


class ProviderStatus(str, Enum):
    """Provider health status.

    - HEALTHY: Provider is functioning normally
    - UNHEALTHY: Provider has exceeded failure threshold
    - DISABLED: Provider is manually disabled
    """

    HEALTHY = "healthy"  # 健康
    UNHEALTHY = "unhealthy"  # 不健康
    DISABLED = "disabled"  # 已禁用


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider.

    This model defines the configuration for one LLM provider in the proxy,
    including authentication, routing parameters, and failure detection settings.
    """

    name: str  # Provider 名称（唯一标识符）
    provider: str  # Provider 类型 (anthropic/openai/doubao)
    api_key: str  # API Key for authentication
    api_base: str  # API Base URL
    model: str  # Model name to use
    weight: int = Field(default=1, ge=1)  # 权重（用于 weighted 策略）
    priority: int = Field(default=1, ge=1)  # 优先级（用于 priority/failover 策略，数字越小优先级越高）
    enabled: bool = Field(default=True)  # 是否启用该 provider
    max_failures: int = Field(default=3, ge=1)  # 最大连续失败次数
    failure_window: int = Field(default=60, ge=1)  # 故障统计时间窗口（秒）
    recovery_timeout: int = Field(default=300, ge=1)  # 故障恢复超时（秒）


class LLMProxyConfig(BaseModel):
    """LLM Proxy configuration.

    Main configuration model for LLM Proxy, controlling routing strategy,
    health checking, and provider list.
    """

    enabled: bool = Field(default=False)  # 是否启用 Proxy
    strategy: ProxyStrategy = Field(default=ProxyStrategy.FAILOVER)  # 路由策略
    retry_count: int = Field(default=3, ge=0)  # 全局重试次数
    health_check_interval: int = Field(
        default=30, ge=0
    )  # 健康检查间隔（秒），0表示禁用
    circuit_breaker_threshold: int = Field(default=5, ge=1)  # 熔断器阈值
    circuit_breaker_timeout: int = Field(default=60, ge=1)  # 熔断器超时（秒）
    providers: list[ProviderConfig] = Field(default_factory=list)  # Provider 列表
