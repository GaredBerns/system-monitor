"""API rate limiting for C2 Server"""
import time
from functools import wraps
from collections import defaultdict
from threading import Lock
from flask import request, jsonify

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = Lock()
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """Check if request is allowed"""
        now = time.time()
        
        with self.lock:
            # Clean old requests
            self.requests[key] = [t for t in self.requests[key] if now - t < window]
            
            # Check limit
            if len(self.requests[key]) >= limit:
                return False
            
            # Add request
            self.requests[key].append(now)
            return True
    
    def get_remaining(self, key: str, limit: int, window: int) -> int:
        """Get remaining requests"""
        now = time.time()
        with self.lock:
            self.requests[key] = [t for t in self.requests[key] if now - t < window]
            return max(0, limit - len(self.requests[key]))
    
    def reset(self, key: str):
        """Reset rate limit for key"""
        with self.lock:
            self.requests.pop(key, None)

limiter = RateLimiter()

def rate_limit(limit: int = 100, window: int = 60, key_func=None):
    """Rate limit decorator
    
    Args:
        limit: Max requests per window
        window: Time window in seconds
        key_func: Function to generate rate limit key (default: IP address)
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if key_func:
                key = key_func()
            else:
                key = f"ip:{request.remote_addr}"
            
            if not limiter.is_allowed(key, limit, window):
                return jsonify({
                    "error": "rate_limit_exceeded",
                    "message": f"Max {limit} requests per {window}s"
                }), 429
            
            remaining = limiter.get_remaining(key, limit, window)
            response = f(*args, **kwargs)
            
            # Add rate limit headers
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(int(time.time() + window))
            
            return response
        return wrapped
    return decorator
