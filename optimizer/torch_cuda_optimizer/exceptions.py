"""Custom exceptions for torch-cuda-optimizer."""


class PyDataError(Exception):
    """Base exception for torch-cuda-optimizer."""
    pass


class ValidationError(PyDataError):
    """Data validation error."""
    pass


class CacheError(PyDataError):
    """Cache operation error."""
    pass


class ConfigError(PyDataError):
    """Configuration error."""
    pass


class RemoteError(PyDataError):
    """Remote operation error."""
    pass
