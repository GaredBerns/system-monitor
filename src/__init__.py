"""C2 Server - Multi-platform remote agent management.

Packages:
- agents: Agent implementations (universal, kaggle, cloud, replit)
- autoreg: Auto-registration engine
- c2: C2 server core
- core: Configuration, secrets, health checks
- mail: Temporary email services
- utils: Common utilities, logging, validation
"""

__version__ = "4.0.0"
__author__ = "C2 Server"

# Lazy imports to avoid circular dependencies
__all__ = [
    # Agents
    "BaseAgent",
    "UniversalAgent",
    "get_kaggle_agent",
    "get_cloud_miners",
    # Auto-registration
    "job_manager",
    "account_store",
    "PLATFORMS",
    # Mail
    "mail_manager",
    "get_domains",
    # Core
    "Config",
    "get_secrets_manager",
    # Utils
    "get_logger",
    "generate_identity",
]

def __getattr__(name):
    """Lazy import on access."""
    if name in ("BaseAgent", "UniversalAgent", "get_kaggle_agent", "get_cloud_miners"):
        from . import agents
        if name == "BaseAgent":
            return agents.BaseAgent
        elif name == "UniversalAgent":
            return agents.UniversalAgent
        elif name == "get_kaggle_agent":
            return agents.get_kaggle_agent
        elif name == "get_cloud_miners":
            return agents.get_cloud_miners
    elif name in ("job_manager", "account_store", "PLATFORMS"):
        from . import autoreg
        return getattr(autoreg, name)
    elif name in ("mail_manager", "get_domains"):
        from . import mail
        return getattr(mail, name)
    elif name == "Config":
        from .core.config import Config
        return Config
    elif name == "get_secrets_manager":
        from .core.secrets import get_secrets_manager
        return get_secrets_manager
    elif name in ("get_logger", "generate_identity"):
        from .utils import get_logger, generate_identity
        return get_logger if name == "get_logger" else generate_identity
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")