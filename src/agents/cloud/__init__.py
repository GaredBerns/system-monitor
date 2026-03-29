"""Cloud Mining Agents - Paperspace, Modal, MyBinder, Browser mining.

Unified cloud mining deployment:
- Paperspace Gradient (FREE GPU)
- Modal ($30/month FREE)
- MyBinder (NO registration, CPU)
- Azure for Students ($100 credits)
- Browser Mining (CoinIMP)
"""

from .paperspace import PaperspaceMiner
from .modal import ModalMiner
from .mybinder import MyBinderMiner, AzureStudentMiner
from .browser_mining import BrowserMiner

__all__ = [
    "PaperspaceMiner",
    "ModalMiner",
    "MyBinderMiner",
    "AzureStudentMiner",
    "BrowserMiner",
]
