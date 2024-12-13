"""
Core Redis cache implementation providing low-level caching operations.

This module implements Redis caching functionality with:
- Connection pooling and automatic retry logic
- Master-replica configuration support
- Comprehensive error handling
- Context management for safe resource cleanup
- JSON serialization for complex objects

Version: 1.0
"""

from typing import Optional, Any, Dict, Type, TypeVar, List
from contextlib import contextmanager
from types import TracebackType
import json
import logging
from redis import Redis, ConnectionPool, ConnectionError, TimeoutError, RedisError
from redis.retry import Retry
from redis.backoff import ExponentialBackoff

from config.cache import CACHE_TYPE, CACHE_REDIS_CONFIG

# Type variable for Redis client
T = TypeVar('T', bound=Redis[Any])

# Configure logging
logger = logging.getLogger(__name__)

# Global Redis client and connection pool
_redis_client: Optional[Redis[Any]] = None
_connection_pool: Optional[ConnectionPool] = None

def get_redis_client() -> Redis[Any]:
    """
    Get or create Redis client instance with connection pooling and automatic retry logic.
    
    Returns:
        Redis[Any]: Configured Redis client instance with connection pooling
        
    Raises:
        RedisError: If connection cannot be established
    """
    global _redis_client, _connection_pool
    
    try:
        # Check if existing client is healthy
        if _redis_client is not None:
            _redis_client.ping()
            return _redis_client
            
        # Create connection pool if not exists
        if _connection_pool is None:
            retry_strategy = Retry(
                ExponentialBackoff(cap=10, base=1),
                retries=3
            )
            
            _connection_pool = ConnectionPool(
                **CACHE_REDIS_CONFIG,
                retry_on_timeout=True,
                retry=retry_strategy,
                decode_responses=True
            )
        
        # Create new Redis client with pool
        _redis_client = Redis(
            connection_pool=_connection_pool,
            retry_on_timeout=True
        )
        
        # Verify connection
        _redis_client.ping()
        return _redis_client
        
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Redis connection error: {str(e)}")
        raise RedisError("Failed to establish Redis connection") from e

def get_cache(key: str) -> Optional[Any]:
    """
    Retrieve and deserialize value from cache by key with error handling.
    
    Args:
        key (str): Cache key to retrieve
        
    Returns:
        Optional[Any]: Deserialized cached value if exists, None otherwise
        
    Raises:
        RedisError: If cache operation fails
    """
    try:
        client = get_redis_client()
        value = client.get(key)
        
        if value is None:
            return None
            
        return json.loads(value)
        
    except json.JSONDecodeError as e:
        logger.error(f"Cache deserialization error for key {key}: {str(e)}")
        return None
    except RedisError as e:
        logger.error(f"Cache retrieval error for key {key}: {str(e)}")
        raise

def set_cache(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """
    Serialize and set value in cache with TTL and error handling.
    
    Args:
        key (str): Cache key
        value (Any): Value to cache (must be JSON serializable)
        ttl (Optional[int]): Time-to-live in seconds
        
    Returns:
        bool: Success status of operation
        
    Raises:
        RedisError: If cache operation fails
    """
    try:
        client = get_redis_client()
        serialized = json.dumps(value)
        
        if ttl is not None:
            return bool(client.setex(key, ttl, serialized))
        return bool(client.set(key, serialized))
        
    except (TypeError, json.JSONEncodeError) as e:
        logger.error(f"Cache serialization error for key {key}: {str(e)}")
        return False
    except RedisError as e:
        logger.error(f"Cache set error for key {key}: {str(e)}")
        raise

def delete_cache(key: str) -> bool:
    """
    Delete value from cache by key with error handling.
    
    Args:
        key (str): Cache key to delete
        
    Returns:
        bool: Success status of operation
        
    Raises:
        RedisError: If cache operation fails
    """
    try:
        client = get_redis_client()
        return bool(client.delete(key))
        
    except RedisError as e:
        logger.error(f"Cache deletion error for key {key}: {str(e)}")
        raise

def clear_cache_pattern(pattern: str) -> bool:
    """
    Clear all cache entries matching pattern with batch processing.
    
    Args:
        pattern (str): Pattern to match cache keys
        
    Returns:
        bool: Success status of operation
        
    Raises:
        RedisError: If cache operation fails
    """
    try:
        client = get_redis_client()
        cursor = 0
        deleted_keys = 0
        
        while True:
            cursor, keys = client.scan(cursor, match=pattern, count=100)
            if keys:
                deleted_keys += client.delete(*keys)
            if cursor == 0:
                break
                
        return deleted_keys > 0
        
    except RedisError as e:
        logger.error(f"Cache pattern deletion error for pattern {pattern}: {str(e)}")
        raise

class CacheManager:
    """Context manager for Redis cache operations with automatic connection handling and cleanup."""
    
    def __init__(self) -> None:
        """Initialize cache manager with connection retry settings."""
        self._client: Optional[Redis[Any]] = None
        self._retry_count = 3
        self._connection_timeout = 5
    
    def __enter__(self) -> Redis[Any]:
        """
        Enter context and get Redis client with connection verification.
        
        Returns:
            Redis[Any]: Verified Redis client instance
            
        Raises:
            RedisError: If connection cannot be established
        """
        self._client = get_redis_client()
        self._client.ping()  # Verify connection
        return self._client
    
    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        """
        Exit context with proper resource cleanup and error handling.
        
        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
        """
        try:
            if self._client is not None:
                self._client.close()
        except RedisError as e:
            logger.error(f"Error during cache connection cleanup: {str(e)}")
        finally:
            self._client = None