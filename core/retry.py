#!/usr/bin/env python3
"""Retry utilities with exponential backoff and circuit breaker."""

import time
import functools
from typing import Callable, Any, Optional, Tuple, Type
from datetime import datetime, timedelta

class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass

class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass

def exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for retry with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Add random jitter to delay
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        raise RetryError(
                            f"Failed after {max_retries} retries: {str(e)}"
                        ) from e
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # Add jitter
                    if jitter:
                        import random
                        delay = delay * (0.5 + random.random())
                    
                    print(f"[Retry] Attempt {attempt + 1}/{max_retries} failed: {e}")
                    print(f"[Retry] Waiting {delay:.2f}s before retry...")
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failure threshold exceeded, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker is OPEN. "
                    f"Retry after {self._time_until_retry():.0f}s"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return (datetime.now() - self.last_failure_time).seconds >= self.recovery_timeout
    
    def _time_until_retry(self) -> float:
        """Calculate seconds until retry is allowed."""
        if self.last_failure_time is None:
            return 0
        elapsed = (datetime.now() - self.last_failure_time).seconds
        return max(0, self.recovery_timeout - elapsed)
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            print(f"[CircuitBreaker] OPEN - {self.failure_count} failures")


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """Decorator for circuit breaker pattern."""
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=exceptions[0] if exceptions else Exception
    )
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


# Example usage and tests
if __name__ == "__main__":
    # Test exponential backoff
    @exponential_backoff(max_retries=3, base_delay=0.5)
    def flaky_function(fail_count=2):
        """Function that fails first N times."""
        if not hasattr(flaky_function, 'attempts'):
            flaky_function.attempts = 0
        
        flaky_function.attempts += 1
        
        if flaky_function.attempts <= fail_count:
            raise ConnectionError(f"Attempt {flaky_function.attempts} failed")
        
        return "Success!"
    
    try:
        result = flaky_function(fail_count=2)
        print(f"Result: {result}")
    except RetryError as e:
        print(f"Failed: {e}")
    
    # Test circuit breaker
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5)
    
    def unreliable_service():
        raise ConnectionError("Service unavailable")
    
    for i in range(5):
        try:
            breaker.call(unreliable_service)
        except (ConnectionError, CircuitBreakerOpen) as e:
            print(f"Call {i+1}: {type(e).__name__}: {e}")
