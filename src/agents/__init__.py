"""Agents package - all agent types.

Structure:
- base: Base classes (BaseAgent, UniversalAgent)
- universal: Full-featured universal C2 agent
- kaggle: Kaggle-specific agents (C2, datasets)
- cloud: Cloud mining agents (Paperspace, Modal, MyBinder, Browser)
- replit: Replit platform agent
- browser: Browser automation utilities
"""

from .base import BaseAgent, UniversalAgent
from .universal import UniversalAgent as FullAgent

# Lazy imports for submodules
__all__ = [
    "BaseAgent",
    "UniversalAgent", 
    "FullAgent",
]

def get_kaggle_agent():
    """Get Kaggle C2 agent."""
    from .kaggle import KaggleC2Agent
    return KaggleC2Agent

def get_cloud_miners():
    """Get cloud mining agents."""
    from .cloud import PaperspaceMiner, ModalMiner, MyBinderMiner, AzureStudentMiner, BrowserMiner
    return {
        "paperspace": PaperspaceMiner,
        "modal": ModalMiner,
        "mybinder": MyBinderMiner,
        "azure_student": AzureStudentMiner,
        "browser": BrowserMiner,
    }

