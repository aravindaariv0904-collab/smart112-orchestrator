"""
Rate Limiting Middleware for FastAPI

Provides token bucket and sliding window rate limiting for:
- Authentication endpoints (login, token refresh)
- Sensitive operations (password change, user deletion)
- API endpoints (configurable limits)

Supports both in-memory and Redis-backed rate limiting.
- In-memory: Single-process only, doesn't survive restarts
- Redis-backed: Distributed, survives restarts, multi-worker support

Configuration:
- RATE_LIMIT_STRATEGY: "memory" (default) or "redis"
- When Redis is unavailable, falls back to in-memory implementation

================================================================================
"""

import logging
import time
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable, Optional, Tuple
from functools import wraps

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("smart112.rate_limit")

# Import Redis client (will be None if not available)
try:
    from backend.app.core.redis_client import get_redis
    _redis_available = True
except ImportError:
    get_redis = lambda: None
    _redis_available = False


@dataclass
class RateLimitConfig:
    """Rate limit configuration for an endpoint or pattern."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10  # Max requests in a short burst
    block_duration_seconds: int = 60  # How long to block after limit exceeded


# Default rate limits by endpoint pattern
DEFAULT_LIMITS = {
    "/api/v1/auth/login": RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        burst_size=5,
        block_duration_seconds=300,  # 5 min block for brute force protection
    ),
    "/api/v1/auth/refresh": RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=500,
        burst_size=10,
        block_duration_seconds=60,
    ),
    "/api/v1/auth/verify": RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_size=20,
        block_duration_seconds=30,
    ),
    "/api/v1/users/{user_id}/change-password": RateLimitConfig(
        requests_per_minute=5,
        requests_per_hour=20,
        burst_size=3,
        block_duration_seconds=300,
    ),
    "/api/v1/users/{user_id}": RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=500,
        burst_size=10,
        block_duration_seconds=60,
    ),
    "/api/v1/users": RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_size=20,
        block_duration_seconds=60,
    ),
    "/api/v1/notifications": RateLimitConfig(
        requests_per_minute=120,
        requests_per_hour=2000,
        burst_size=30,
        block_duration_seconds=60,
    ),
}


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter implementation.
    
    Supports both in-memory and Redis-backed storage.
    - In-memory: Single-process only, doesn't survive restarts
    - Redis-backed: Distributed, survives restarts, multi-worker support
    
    When Redis is available and RATE_LIMIT_STRATEGY="redis", uses Redis.
    Otherwise falls back to in-memory implementation.
    """
    
    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._blocks: dict[str, float] = {}  # Key -> unblock time
        self._lock = Lock()
        self._configs: dict[str, RateLimitConfig] = dict(DEFAULT_LIMITS)
        self._use_redis = False
        self._redis_client = None
        self._strategy = "memory"  # "memory" or "redis"
    
    def set_config(self, key: str, config: RateLimitConfig) -> None:
        """Set rate limit configuration for a key pattern."""
        self._configs[key] = config
    
    def use_redis(self, redis_client) -> None:
        """Enable Redis-backed rate limiting."""
        if redis_client and redis_client.is_connected:
            self._use_redis = True
            self._redis_client = redis_client
            self._strategy = "redis"
            logger.info("Rate limiter switched to Redis-backed mode")
        else:
            logger.warning("Redis not available, staying in memory mode")
    
    def _get_config_for_key(self, key: str) -> RateLimitConfig:
        """Get the most specific config for a key."""
        # Try exact match first
        if key in self._configs:
            return self._configs[key]
        
        # Try pattern matching (simple prefix matching)
        for pattern, config in self._configs.items():
            if key.startswith(pattern.rstrip("{").rstrip("}").split("{")[0] if "{" in pattern else pattern):
                return config
            if pattern in key:
                return config
        
        # Default config
        return RateLimitConfig()
    
    def is_blocked(self, key: str) -> Tuple[bool, Optional[float]]:
        """Check if a key is currently blocked."""
        with self._lock:
            if key in self._blocks:
                unblock_time = self._blocks[key]
                if time.time() < unblock_time:
                    return True, unblock_time - time.time()
                else:
                    # Block expired, remove it
                    del self._blocks[key]
            return False, None
    
    async def check_rate_limit(
        self,
        key: str,
        config: Optional[RateLimitConfig] = None,
    ) -> Tuple[bool, dict]:
        """
        Check if a request is allowed under rate limits.
        
        Uses Redis when available and configured, otherwise uses in-memory storage.
        
        Returns:
            (allowed, info) where info contains:
            - remaining: requests remaining in current window
            - reset_seconds: seconds until window resets
            - limit: configured limit
            - blocked: whether blocked and for how long
        """
        config = config or self._get_config_for_key(key)
        
        # Use Redis if available and configured
        if self._use_redis and self._redis_client:
            try:
                return await self._check_rate_limit_redis(key, config)
            except Exception as e:
                logger.error("Redis rate limit check failed: %s. Falling back to memory.", e)
                return self._check_rate_limit_memory(key, config)
        
        # Fall back to in-memory implementation
        return self._check_rate_limit_memory(key, config)
    
    def _check_rate_limit_memory(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> Tuple[bool, dict]:
        """In-memory rate limit check (single-process only)."""
        with self._lock:
            # Check if blocked
            if key in self._blocks:
                unblock_time = self._blocks[key]
                if time.time() < unblock_time:
                    remaining_wait = unblock_time - time.time()
                    logger.warning(
                        "Rate limit exceeded for %s, blocking for %.1fs",
                        key, remaining_wait
                    )
                    return False, {
                        "allowed": False,
                        "remaining": 0,
                        "reset_seconds": remaining_wait,
                        "limit": config.requests_per_minute,
                        "blocked": True,
                        "block_duration": remaining_wait,
                    }
                else:
                    del self._blocks[key]
            
            # Clean old timestamps outside the window
            now = time.time()
            window_start = now - 60  # 1-minute window
            
            # Remove timestamps older than 1 minute
            self._windows[key] = [
                ts for ts in self._windows[key] 
                if ts > window_start
            ]
            
            # Check per-minute limit
            request_count = len(self._windows[key])
            
            if request_count >= config.requests_per_minute:
                # Block the key
                self._blocks[key] = now + config.block_duration_seconds
                logger.warning(
                    "Rate limit exceeded for %s (%d requests/min, limit: %d)",
                    key, request_count, config.requests_per_minute
                )
                return False, {
                    "allowed": False,
                    "remaining": 0,
                    "reset_seconds": config.block_duration_seconds,
                    "limit": config.requests_per_minute,
                    "blocked": True,
                    "block_duration": config.block_duration_seconds,
                }
            
            # Check burst limit (shorter window)
            burst_window_start = now - 5  # 5-second burst window
            burst_count = sum(1 for ts in self._windows[key] if ts > burst_window_start)
            
            if burst_count >= config.burst_size:
                # Still allow but with warning
                logger.warning(
                    "Burst limit near for %s (%d requests in 5s, limit: %d)",
                    key, burst_count, config.burst_size
                )
            
            # Record this request
            self._windows[key].append(now)
            
            # Calculate remaining and reset
            remaining = config.requests_per_minute - request_count - 1
            # Find oldest request in window for reset time
            if self._windows[key]:
                oldest = min(self._windows[key])
                reset_seconds = 60 - (now - oldest)
            else:
                reset_seconds = 60
            
            return True, {
                "allowed": True,
                "remaining": max(0, remaining),
                "reset_seconds": max(1, int(reset_seconds)),
                "limit": config.requests_per_minute,
                "blocked": False,
            }
    
    async def _check_rate_limit_redis(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> Tuple[bool, dict]:
        """Redis-backed rate limit check (distributed, multi-worker)."""
        if not self._redis_client:
            # Fall back to memory if Redis not available
            return self._check_rate_limit_memory(key, config)
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self._redis_client.client.pipeline()
            now = time.time()
            window_start = now - 60  # 1-minute window
            
            # Remove old timestamps and get count
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = await pipe.execute()
            
            current_count = results[1]
            
            if current_count >= config.requests_per_minute:
                # Block the key with TTL
                block_key = f"{key}:block"
                await self._redis_client.client.setex(
                    block_key, config.block_duration_seconds, "1"
                )
                logger.warning(
                    "Rate limit exceeded for %s (%d requests/min, limit: %d)",
                    key, current_count, config.requests_per_minute
                )
                return False, {
                    "allowed": False,
                    "remaining": 0,
                    "reset_seconds": config.block_duration_seconds,
                    "limit": config.requests_per_minute,
                    "blocked": True,
                    "block_duration": config.block_duration_seconds,
                }
            
            # Check burst limit
            burst_window_start = now - 5
            pipe = self._redis_client.client.pipeline()
            pipe.zremrangebyscore(key, 0, burst_window_start)
            pipe.zcard(key)
            burst_results = await pipe.execute()
            burst_count = burst_results[1]
            
            if burst_count >= config.burst_size:
                logger.warning(
                    "Burst limit near for %s (%d requests in 5s, limit: %d)",
                    key, burst_count, config.burst_size
                )
            
            # Record this request
            await self._redis_client.client.zadd(key, {f"req_{now}": now})
            await self._redis_client.client.expire(key, 60)
            
            remaining = config.requests_per_minute - current_count - 1
            reset_seconds = 60  # Approximate
            
            return True, {
                "allowed": True,
                "remaining": max(0, remaining),
                "reset_seconds": max(1, int(reset_seconds)),
                "limit": config.requests_per_minute,
                "blocked": False,
            }
        except Exception as e:
            logger.error("Redis rate limit check failed for %s: %s. Falling back to memory.", key, e)
            # Fall back to memory on Redis error
            return self._check_rate_limit_memory(key, config)
    
    def get_remaining(self, key: str) -> int:
        """Get remaining requests for a key."""
        with self._lock:
            now = time.time()
            window_start = now - 60
            self._windows[key] = [
                ts for ts in self._windows[key] 
                if ts > window_start
            ]
            config = self._get_config_for_key(key)
            return max(0, config.requests_per_minute - len(self._windows[key]))


# Global rate limiter instance
# In production with multiple workers, replace with RedisRateLimiter
rate_limiter = SlidingWindowRateLimiter()

# Enable/disable rate limiting (can be set via environment variable)
RATE_LIMIT_ENABLED = True  # Set to False to disable in development


def init_rate_limiter() -> None:
    """Initialize rate limiter with default configurations."""
    if not RATE_LIMIT_ENABLED:
        logger.info("Rate limiting is DISABLED")
        return
    
    for pattern, config in DEFAULT_LIMITS.items():
        rate_limiter.set_config(pattern, config)
    logger.info("Rate limiter initialized with %d endpoint configurations", len(DEFAULT_LIMITS))


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Get the global rate limiter instance."""
    global rate_limiter
    
    # Try to enable Redis if available and configured
    if RATE_LIMIT_STRATEGY == "redis" and _redis_available:
        redis_client = get_redis()
        if redis_client and redis_client.is_connected:
            rate_limiter.use_redis(redis_client)
    
    return rate_limiter





class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply rate limiting to all requests."""
    
    def __init__(self, app, exempt_paths: Optional[list[str]] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or ["/health", "/docs", "/openapi.json", "/redoc"]
    
    async def dispatch(self, request: Request, call_next):
        # Skip if rate limiting disabled
        if not RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Skip exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)
        
        # Generate rate limit key
        rate_key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
        
        # Check rate limit
        allowed, info = await rate_limiter.check_rate_limit(rate_key)
        
        if not allowed:
            response = await call_next(request)
            response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
            response.headers["Retry-After"] = str(int(info["block_duration"]))
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + info["reset_seconds"]))
            response.body = b"Rate limit exceeded. Please try again later."
            return response
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = rate_limiter.get_remaining(rate_key)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response


# IP-based rate limiting helper
def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (for proxied requests)
    if "X-Forwarded-For" in request.headers:
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    if "X-Real-IP" in request.headers:
        return request.headers["X-Real-IP"]
    
    # Fall back to client host
    if request.client:
        return request.client.host
    return "unknown"


# User-based rate limiting helper
def get_user_rate_key(request: Request, user_id: str) -> str:
    """Generate rate limit key based on user ID."""
    return f"user:{user_id}:{request.url.path}"


# Auth-specific rate limiting
def get_auth_rate_key(request: Request, username: Optional[str] = None) -> str:
    """Generate rate limit key for authentication endpoints."""
    ip = get_client_ip(request)
    endpoint = request.url.path
    if username:
        return f"{endpoint}:{username.strip().lower()}:{ip}"
    return f"{endpoint}:{ip}"


# Clear rate limit for a key (e.g., after successful authentication)
def clear_rate_limit(key: str) -> None:
    """Clear rate limit data for a key."""
    with rate_limiter._lock:
        if key in rate_limiter._windows:
            del rate_limiter._windows[key]
        if key in rate_limiter._blocks:
            del rate_limiter._blocks[key]
