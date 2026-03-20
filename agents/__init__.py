"""C2 Agents package."""

from .agent_linux import LinuxAgent
from .agent_macos import MacAgent  
from .agent_colab import ColabAgent
from .kaggle_agent import KaggleAgent

__all__ = [
    'LinuxAgent',
    'MacAgent', 
    'ColabAgent',
    'KaggleAgent',
]
