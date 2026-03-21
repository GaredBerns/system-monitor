"""Redis caching layer for C2 Server"""
import redis
import json
import pickle
from functools import wraps
from typing import Any, Optional, Callable
import hashlib

class CacheManager:
    def __init__(self, host='localhost', port=6379, db=0, default_ttl=300):
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=False)
        self.default_ttl = default_ttl
        
    def get(self, key: str) -> Optional[Any]:
        data = self.redis.get(key)
        return pickle.loads(data) if data else None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        ttl = ttl or self.default_ttl
        self.redis.setex(key, ttl, pickle.dumps(value))
    
    def delete(self, key: str):
        self.redis.delete(key)
    
    def clear_pattern(self, pattern: str):
        for key in self.redis.scan_iter(match=pattern):
            self.redis.delete(key)
    
    def exists(self, key: str) -> bool:
        return self.redis.exists(key) > 0

cache = CacheManager()

def cached(ttl: int = 300, key_prefix: str = ''):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(':'.join(key_parts).encode()).hexdigest()
            
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern: str):
    cache.clear_pattern(pattern)
