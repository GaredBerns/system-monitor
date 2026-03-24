"""Utility functions for torch-cuda-optimizer."""

import os
import hashlib
from typing import Any, Dict, List


def ensure_dir(path: str) -> str:
    """Ensure directory exists, create if needed.
    
    Args:
        path: Directory path
        
    Returns:
        Absolute path
    """
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


def file_hash(path: str, algorithm: str = "md5") -> str:
    """Calculate file hash.
    
    Args:
        path: File path
        algorithm: Hash algorithm (md5, sha1, sha256)
        
    Returns:
        Hex digest string
    """
    h = hashlib.new(algorithm)
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Override dictionary
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def flatten_list(nested: List) -> List:
    """Flatten nested list.
    
    Args:
        nested: Nested list
        
    Returns:
        Flat list
    """
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        else:
            result.append(item)
    return result
