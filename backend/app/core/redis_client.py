"""
Redis Client for Stage 9 Integration

Provides Redis connection management for:
- Distributed rate limiting (replaces in-memory rate limiter)
- WebSocket real-time messaging (pub/sub)
- Session caching
- Real-time event broadcasting

TODO: Replace in-memory rate limiter with Redis-based implementation
TODO: Add WebSocket pub/sub for real-time updates
TODO: Add session caching for JWT tokens
"""

import logging
from typing import Optional, Any

import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool

from backend.app.core.config import settings

logger = logging.getLogger("smart112.redis")


class RedisClient:
    """Async Redis client wrapper with connection pooling."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        pool_size: int = 10,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        retry_on_timeout: bool = True,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.pool_size = pool_size
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None
        self._connected = False

    async def connect(self) -> None:
        """Initialize Redis connection pool and client."""
        if self._connected:
            return

        try:
            self._pool = ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.pool_size,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                retry_on_timeout=retry_on_timeout,
                decode_responses=True,
            )
            self._client = redis.Redis(connection_pool=self._pool)

            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info(
                "Redis connected: %s:%d (db=%d, pool_size=%d)",
                self.host, self.port, self.db, self.pool_size
            )
        except Exception as e:
            logger.warning("Redis connection failed: %s. Rate limiting disabled.", e)
            self._connected = False
            self._client = None
            self._pool = None

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
            self._client = None
            self._connected = False
            logger.info("Redis connection closed")

    @property
    def client(self) -> Optional[Redis]:
        """Get Redis client instance."""
        return self._client

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected and self._client is not None

    # =========================================================================
    # Basic Operations (for testing connectivity)
    # =========================================================================

    async def set(self, key: str, value: str, expire_seconds: Optional[int] = None) -> bool:
        """Set a key-value pair with optional expiration."""
        if not self.is_connected:
            return False
        try:
            if expire_seconds:
                await self._client.setex(key, expire_seconds, value)
            else:
                await self._client.set(key, value)
            return True
        except Exception as e:
            logger.error("Redis SET failed for key %s: %s", key, e)
            return False

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self.is_connected:
            return None
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.error("Redis GET failed for key %s: %s", key, e)
            return None

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        if not self.is_connected:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.error("Redis DELETE failed for key %s: %s", key, e)
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.is_connected:
            return False
        try:
            return await self._client.exists(key) > 0
        except Exception as e:
            logger.error("Redis EXISTS failed for key %s: %s", key, e)
            return False

    # =========================================================================
    # Pub/Sub for WebSocket Real-Time Messaging
    # =========================================================================

    async def publish(self, channel: str, message: str) -> int:
        """Publish a message to a Redis channel."""
        if not self.is_connected:
            logger.warning("Cannot publish to %s: Redis not connected", channel)
            return 0
        try:
            subscribers = await self._client.publish(channel, message)
            logger.debug("Published to %s: %d subscribers", channel, subscribers)
            return subscribers
        except Exception as e:
            logger.error("Redis PUBLISH failed for channel %s: %s", channel, e)
            return 0

    async def subscribe(self, channel: str):
        """Subscribe to a Redis channel and return pubsub object."""
        if not self.is_connected:
            logger.warning("Cannot subscribe to %s: Redis not connected", channel)
            return None
        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(channel)
            logger.debug("Subscribed to channel: %s", channel)
            return pubsub
        except Exception as e:
            logger.error("Redis SUBSCRIBE failed for channel %s: %s", channel, e)
            return None

    async def unsubscribe(self, pubsub, channel: str) -> None:
        """Unsubscribe from a Redis channel."""
        if not self.is_connected or not pubsub:
            return
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            logger.debug("Unsubscribed from channel: %s", channel)
        except Exception as e:
            logger.error("Redis UNSUBSCRIBE failed for channel %s: %s", channel, e)

    # =========================================================================
    # Rate Limiting Operations (for Stage 9 Redis-based rate limiter)
    # =========================================================================

    async def rate_limit_sliding_window(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check rate limit using Redis sorted set (sliding window).

        Args:
            key: Rate limit key (e.g., "rate_limit:/api/v1/auth/login:127.0.0.1")
            limit: Maximum requests allowed in window
            window_seconds: Window duration in seconds

        Returns:
            Tuple of (allowed, remaining, reset_seconds)
        """
        if not self.is_connected:
            # Fail open - allow request if Redis is down
            return True, limit, window_seconds

        try:
            now = time.time()
            window_start = now - window_seconds

            # Use pipeline for atomic operations
            pipe = self._client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {f"req_{now}": now})
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

            current_count = results[1]

            if current_count >= limit:
                # Calculate reset time (oldest request in window)
                oldest = await self._client.zrange(key, 0, 0, withscores=True)
                reset_seconds = int(now - oldest[0][1]) + 1 if oldest else window_seconds
                return False, 0, reset_seconds

            remaining = limit - current_count - 1
            return True, max(0, remaining), window_seconds

        except Exception as e:
            logger.error("Redis rate limit check failed for key %s: %s", key, e)
            # Fail open
            return True, limit, window_seconds

    async def rate_limit_counter(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check rate limit using Redis counter (fixed window).

        Args:
            key: Rate limit key
            limit: Maximum requests allowed in window
            window_seconds: Window duration in seconds

        Returns:
            Tuple of (allowed, remaining, reset_seconds)
        """
        if not self.is_connected:
            # Fail open - allow request if Redis is down
            return True, limit, window_seconds

        try:
            current = await self._client.get(key)
            current_count = int(current) if current else 0

            if current_count >= limit:
                # Get TTL for reset time
                ttl = await self._client.ttl(key)
                reset_seconds = ttl if ttl > 0 else window_seconds
                return False, 0, reset_seconds

            # Increment counter
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            await pipe.execute()

            remaining = limit - current_count - 1
            return True, max(0, remaining), window_seconds

        except Exception as e:
            logger.error("Redis rate limit counter failed for key %s: %s", key, e)
            # Fail open
            return True, limit, window_seconds


# Global Redis client instance
redis_client: Optional[RedisClient] = None


async def init_redis() -> RedisClient:
    """Initialize and return the global Redis client."""
    global redis_client

    if redis_client is None:
        redis_client = RedisClient(
            host=settings.redis_host or "localhost",
            port=settings.redis_port or 6379,
            db=settings.redis_db or 0,
            password=settings.redis_password,
            pool_size=settings.redis_pool_size or 10,
        )
        await redis_client.connect()

    return redis_client


async def close_redis() -> None:
    """Close the global Redis client."""
    global redis_client

    if redis_client:
        await redis_client.close()
        redis_client = None


def get_redis() -> Optional[RedisClient]:
    """Get the global Redis client instance."""
    return redis_client


# Import time for rate limiting operations
import time
