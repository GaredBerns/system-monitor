"""C2 Server Core - Main server and communication channels.

Components:
- server: Flask application with all routes
- models: Database models (Base, User, Agent, Task, Log, Listener, Config)
- orchestrator: Task orchestration
- autonomous_miner: Autonomous mining controller
- dataset_c2_server: Dataset-based C2 server
- dataset_c2_poller: Dataset C2 poller
- telegram_poller: Telegram C2 poller
"""

__all__ = ["Base", "User", "Agent", "Task", "Log", "Listener", "Config", "Orchestrator"]

def __getattr__(name):
    """Lazy import on access."""
    if name == "Base":
        from .models import Base
        return Base
    elif name == "User":
        from .models import User
        return User
    elif name == "Agent":
        from .models import Agent
        return Agent
    elif name == "Task":
        from .models import Task
        return Task
    elif name == "Log":
        from .models import Log
        return Log
    elif name == "Listener":
        from .models import Listener
        return Listener
    elif name == "Config":
        from .models import Config as ConfigModel
        return ConfigModel
    elif name == "Orchestrator":
        from .orchestrator import Orchestrator
        return Orchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")