"""
AI Solution Builder — In-Memory Rate Limiter

Provides sliding-window rate limiting without Redis dependency.
Falls back to this when Redis is unavailable.
"""

import time
import threading
from collections import defaultdict
from typing import Optional


class InMemoryRateLimiter:
    """
    Thread-safe in-memory sliding window rate limiter.
    
    Tracks request timestamps per key and enforces limits within
    a rolling time window. Old entries are pruned on access.
    """
    
    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._cleanup_interval = 300  # seconds
        self._last_cleanup = time.time()
    
    def _cleanup(self) -> None:
        """Remove entries older than the window."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        
        cutoff = now - 3600  # 1 hour max retention
        keys_to_remove = []
        for key, timestamps in self._windows.items():
            self._windows[key] = [t for t in timestamps if t > cutoff]
            if not self._windows[key]:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._windows[key]
    
    def check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, dict]:
        """
        Check if a request is allowed under the rate limit.
        
        Args:
            key: Unique identifier (e.g., user ID, IP address)
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (allowed, info_dict)
            info_dict contains: limit, remaining, reset_at, retry_after
        """
        now = time.time()
        
        with self._lock:
            self._cleanup()
            
            # Get timestamps for this key within the window
            window_start = now - window_seconds
            timestamps = self._windows[key]
            
            # Prune old timestamps
            valid = [t for t in timestamps if t > window_start]
            self._windows[key] = valid
            
            remaining = max(0, max_requests - len(valid))
            reset_at = (valid[0] + window_seconds) if valid else now + window_seconds
            
            if len(valid) >= max_requests:
                retry_after = max(1, int(valid[0] + window_seconds - now))
                return False, {
                    'limit': max_requests,
                    'remaining': 0,
                    'reset_at': int(reset_at),
                    'retry_after': retry_after,
                }
            
            # Record this request
            valid.append(now)
            self._windows[key] = valid
            
            return True, {
                'limit': max_requests,
                'remaining': remaining - 1,
                'reset_at': int(reset_at),
                'retry_after': 0,
            }
    
    def reset(self, key: str) -> None:
        """Reset the counter for a specific key."""
        with self._lock:
            self._windows.pop(key, None)
    
    def get_usage(self, key: str, window_seconds: int) -> int:
        """Get the number of requests in the current window."""
        now = time.time()
        with self._lock:
            window_start = now - window_seconds
            timestamps = self._windows.get(key, [])
            return sum(1 for t in timestamps if t > window_start)


# Global singleton
rate_limiter = InMemoryRateLimiter()
