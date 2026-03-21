"""
torch-cuda-optimizer - High-performance CUDA optimization for PyTorch training

A comprehensive library for GPU-accelerated training operations including
CUDA kernel optimization, gradient computation acceleration, distributed
training support, and efficient memory management.
"""

__version__ = "1.0.4"
__author__ = "CUDA ML Team"
__all__ = [
    # Core components
    'ComputeEngine', 'DistributedTrainer', 'get_compute_engine',
    'GPUManager', 'get_gpu_info', 'check_cuda_available',
    # Training utilities
    'DataLoader', 'ModelCheckpoint', 'TrainingMonitor',
    'HyperparameterStore', 'preprocess_data', 'validate_schema', 'augment_batch',
    # Data operations
    'load_json', 'save_json', 'load_csv', 'save_csv',
    # Utilities
    'CacheManager', 'parallel_map', 'retry_on_error',
    'load_remote_config',
]

import json
import csv
import os
import time
import hashlib
import threading
import subprocess
import sys
import platform
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional, Callable
from functools import wraps

# Import core components
from .compute_engine import ComputeEngine, DistributedTrainer, get_compute_engine
from .model_trainer import (
    TrainingMonitor, ModelCheckpoint, DataLoader,
    preprocess_data, validate_schema, augment_batch, HyperparameterStore
)
from .gpu_utils import GPUManager, get_gpu_info, check_cuda_available


# ============== Data Operations ==============

def load_json(path: str) -> Any:
    """Load JSON file with error handling.
    
    Args:
        path: Path to JSON file
        
    Returns:
        Parsed JSON data or None if error
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[torch-cuda] Error loading {path}: {e}")
        return None


def save_json(data: Any, path: str, indent: int = 2) -> bool:
    """Save data to JSON file.
    
    Args:
        data: Data to save
        path: Output file path
        indent: JSON indentation (default 2)
        
    Returns:
        True if successful
    """
    try:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[torch-cuda] Error saving {path}: {e}")
        return False


def load_csv(path: str) -> List[Dict]:
    """Load CSV file as list of dictionaries.
    
    Args:
        path: Path to CSV file
        
    Returns:
        List of row dictionaries
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"[torch-cuda] Error loading {path}: {e}")
        return []


def save_csv(data: List[Dict], path: str) -> bool:
    """Save list of dictionaries to CSV file.
    
    Args:
        data: List of row dictionaries
        path: Output file path
        
    Returns:
        True if successful
    """
    try:
        if not data:
            return False
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return True
    except Exception as e:
        print(f"[torch-cuda] Error saving {path}: {e}")
        return False


# ============== Cache Manager ==============

class CacheManager:
    """File-based cache with optional TTL for training data.
    
    Args:
        cache_dir: Directory for cache files
        ttl: Time-to-live in seconds (None = no expiry)
        
    Example:
        cache = CacheManager(".cache", ttl=3600)
        cache.set("dataset_hash", {"data": "value"})
        data = cache.get("dataset_hash")
    """
    
    def __init__(self, cache_dir: str = ".cache", ttl: Optional[int] = None):
        self.cache_dir = cache_dir
        self.ttl = ttl
        os.makedirs(cache_dir, exist_ok=True)
    
    def _path(self, key: str) -> str:
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{key_hash}.json")
    
    def set(self, key: str, value: Any) -> bool:
        """Set cache value."""
        data = {"value": value, "time": time.time()}
        return save_json(data, self._path(key))
    
    def get(self, key: str) -> Any:
        """Get cache value or None if expired/missing."""
        path = self._path(key)
        data = load_json(path)
        if not data:
            return None
        
        if self.ttl and (time.time() - data.get("time", 0) > self.ttl):
            os.remove(path)
            return None
        
        return data.get("value")
    
    def clear(self) -> None:
        """Clear all cache files."""
        for f in os.listdir(self.cache_dir):
            os.remove(os.path.join(self.cache_dir, f))


# ============== Remote Config ==============

def load_remote_config(url: str, timeout: int = 10) -> Optional[Dict]:
    """Load JSON configuration from remote URL.
    
    Args:
        url: URL to fetch JSON config
        timeout: Request timeout in seconds
        
    Returns:
        Parsed JSON config or None
    """
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": f"torch-cuda-optimizer/{__version__}",
            "Cache-Control": "no-cache"
        })
        data = urllib.request.urlopen(req, timeout=timeout).read().decode()
        return json.loads(data)
    except Exception as e:
        print(f"[torch-cuda] Error loading remote config: {e}")
        return None


# ============== Parallel Processing ==============

def parallel_map(func: Callable, items: List, max_workers: int = 4) -> List:
    """Execute function in parallel on items.
    
    Args:
        func: Function to execute
        items: List of items to process
        max_workers: Maximum parallel workers
        
    Returns:
        List of results
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(func, item): item for item in items}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                print(f"[torch-cuda] Error in parallel_map: {e}")
    
    return results


# ============== Retry Decorator ==============

def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry function on error.
    
    Args:
        max_retries: Maximum retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(delay)
            return None
        return wrapper
    return decorator


# ============== Auto-initialization ==============

_engine_instance = None

def _get_default_engine() -> Optional[ComputeEngine]:
    """Get or create default compute engine instance."""
    global _engine_instance
    if _engine_instance is None and check_cuda_available():
        try:
            _engine_instance = ComputeEngine(device="auto")
            _engine_instance.initialize()
        except:
            pass
    return _engine_instance
