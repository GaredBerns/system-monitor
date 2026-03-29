"""Utilities - Common functions, logging, validation.

Components:
- common: Identity generation, shared utilities
- logger: Structured logging with context
- proxy: Proxy management and rotation
- rate_limit: Rate limiting utilities
- validation: Input validation helpers
"""

from .common import generate_identity
from .logger import get_logger

__all__ = [
    "generate_identity",
    "get_logger",
]