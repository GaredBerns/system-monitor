"""Kaggle C2 integration package."""

try:
    from .transport import KaggleC2Transport, KaggleC2Manager, KaggleMultiKernel
    KAGGLE_AVAILABLE = True
except ImportError:
    KAGGLE_AVAILABLE = False

__all__ = ["KaggleC2Transport", "KaggleC2Manager", "KaggleMultiKernel", "KAGGLE_AVAILABLE"]
