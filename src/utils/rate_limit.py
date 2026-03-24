"""Rate limiting for API endpoints."""
from flask import request, jsonify
from functools import wraps
import time
from collections import defaultdict
from threading import Lock

class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        self._requests = defaultdict(list)
        self._lock = Lock()
    
    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, dict]:
        """Check if request is allowed.
        
        Args:
            key: Identifier (IP, user_id, etc)
            limit: Max requests in window
            window: Time window in seconds
            
        Returns:
            tuple: (allowed: bool, info: dict)
        """
        now = time.time()
        cutoff = now - window
        
        with self._lock:
            # Clean old requests
            self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]
            
            # Check limit
            current = len(self._requests[key])
            if current >= limit:
                retry_after = int(self._requests[key][0] + window - now)
                return False, {
                    "limit": limit,
                    "remaining": 0,
                    "reset": int(self._requests[key][0] + window),
                    "retry_after": retry_after
                }
            
            # Add request
            self._requests[key].append(now)
            
            return True, {
                "limit": limit,
                "remaining": limit - current - 1,
                "reset": int(now + window)
            }
    
    def reset(self, key: str):
        """Reset rate limit for key."""
        with self._lock:
            if key in self._requests:
                del self._requests[key]

# Global limiter
_limiter = RateLimiter()

def rate_limit(limit: int = 60, window: int = 60, key_func=None):
    """Rate limit decorator.
    
    Args:
        limit: Max requests in window
        window: Time window in seconds
        key_func: Function to get rate limit key (default: IP address)
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Get key
            if key_func:
                key = key_func()
            else:
                key = request.remote_addr
            
            # Check rate limit
            allowed, info = _limiter.is_allowed(key, limit, window)
            
            if not allowed:
                response = jsonify({
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded. Try again in {info['retry_after']} seconds.",
                    "retry_after": info["retry_after"]
                })
                response.status_code = 429
                response.headers["X-RateLimit-Limit"] = str(info["limit"])
                response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
                response.headers["X-RateLimit-Reset"] = str(info["reset"])
                response.headers["Retry-After"] = str(info["retry_after"])
                return response
            
            # Add rate limit headers
            response = f(*args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers["X-RateLimit-Limit"] = str(info["limit"])
                response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
                response.headers["X-RateLimit-Reset"] = str(info["reset"])
            
            return response
        return wrapped
    return decorator

def get_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    return _limiter
