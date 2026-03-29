"""Core module - Configuration, secrets, health checks, metrics.

Components:
- config: Central configuration management (Config class)
- secrets: Secure credential storage (SecretsManager, get_secrets_manager)
- health: Health check endpoints (HealthMonitor)
- metrics: Performance metrics collection (MetricsCollector)
- validation: Input validation utilities
"""

__all__ = ["Config", "get_secrets_manager", "HealthMonitor", "MetricsCollector"]

def __getattr__(name):
    """Lazy import on access."""
    if name == "Config":
        from .config import Config
        return Config
    elif name == "get_secrets_manager":
        from .secrets import get_secrets_manager
        return get_secrets_manager
    elif name == "HealthMonitor":
        from .health import HealthMonitor
        return HealthMonitor
    elif name == "MetricsCollector":
        from .metrics import MetricsCollector
        return MetricsCollector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")