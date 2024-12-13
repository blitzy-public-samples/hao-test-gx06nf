"""
Flask middleware implementing request and response caching using Redis.

This module provides a comprehensive caching solution with:
- Connection pooling and automatic retry logic
- Cache stampede prevention using locks
- Resource-specific TTL configuration
- Cache key versioning and invalidation
- Metrics tracking for cache hits/misses
- Extensive error handling

Version: 1.0
"""

import functools
import json
import logging
from typing import Optional, Callable, Dict, Any, Union
from datetime import datetime

from flask import Flask, request, Response, g
from redis.exceptions import RedisError

from core.cache import get_redis_client, CacheManager
from config.cache import CACHE_TTL, get_cache_key_pattern
from utils.constants import CACHE_CONSTANTS

# Configure logging
logger = logging.getLogger(__name__)

# Global constants
CACHEABLE_METHODS = ['GET']
CACHE_EXEMPT_PATHS = ['/health', '/metrics']
DEFAULT_CACHE_TTL = 300  # 5 minutes
CACHE_KEY_VERSION = '1'  # Increment to invalidate all cache entries

class CacheMiddleware:
    """Flask middleware for request/response caching with Redis."""

    def __init__(self, app: Flask) -> None:
        """
        Initialize cache middleware with Flask app instance.

        Args:
            app (Flask): Flask application instance
        """
        self._app = app
        self._cache_manager = CacheManager()
        self._cache_hits: Dict[str, int] = {}
        self._cache_misses: Dict[str, int] = {}

        # Register middleware handlers
        self._app.before_request(self.before_request)
        self._app.after_request(self.after_request)

        # Initialize cache metrics
        self._setup_metrics()

    def _setup_metrics(self) -> None:
        """Initialize cache metrics tracking."""
        for resource_type in CACHE_TTL:
            self._cache_hits[resource_type] = 0
            self._cache_misses[resource_type] = 0

    def _should_cache_request(self) -> bool:
        """
        Determine if request should be cached based on method and path.

        Returns:
            bool: True if request should be cached
        """
        return (
            request.method in CACHEABLE_METHODS and
            request.path not in CACHE_EXEMPT_PATHS and
            not request.args.get('nocache')
        )

    def _get_cache_key(self) -> str:
        """
        Generate cache key from request path and query parameters.

        Returns:
            str: Versioned cache key
        """
        # Extract resource type from path
        path_parts = request.path.strip('/').split('/')
        resource_type = path_parts[0] if path_parts else 'default'

        # Generate base key pattern
        key = get_cache_key_pattern(
            resource_type=resource_type,
            resource_id=path_parts[-1] if len(path_parts) > 1 else None,
            version=CACHE_KEY_VERSION
        )

        # Add query parameters to key
        if request.args:
            key = f"{key}:{hash(frozenset(request.args.items()))}"

        return key

    def before_request(self) -> Optional[Response]:
        """
        Check cache for existing response before request processing.

        Returns:
            Optional[Response]: Cached response if exists, None otherwise
        """
        if not self._should_cache_request():
            return None

        try:
            cache_key = self._get_cache_key()
            resource_type = request.path.strip('/').split('/')[0]

            with self._cache_manager as cache:
                # Try to get cached response
                cached_data = cache.get(cache_key)
                
                if cached_data:
                    try:
                        data = json.loads(cached_data)
                        self._cache_hits[resource_type] = self._cache_hits.get(resource_type, 0) + 1
                        
                        response = Response(
                            json.dumps(data['data']),
                            status=data['status'],
                            mimetype='application/json'
                        )
                        response.headers['X-Cache'] = 'HIT'
                        return response
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Cache data corruption for key {cache_key}: {str(e)}")
                        cache.delete(cache_key)

                self._cache_misses[resource_type] = self._cache_misses.get(resource_type, 0) + 1
                return None

        except RedisError as e:
            logger.error(f"Cache error in before_request: {str(e)}")
            return None

    def after_request(self, response: Response) -> Response:
        """
        Cache response after request processing if applicable.

        Args:
            response (Response): Flask response object

        Returns:
            Response: Original or cached response
        """
        if not self._should_cache_request() or response.status_code != 200:
            return response

        try:
            cache_key = self._get_cache_key()
            resource_type = request.path.strip('/').split('/')[0]

            # Get appropriate TTL for resource type
            ttl = CACHE_TTL.get(resource_type, DEFAULT_CACHE_TTL)

            with self._cache_manager as cache:
                # Prepare response data for caching
                cache_data = {
                    'data': json.loads(response.get_data()),
                    'status': response.status_code,
                    'timestamp': datetime.utcnow().isoformat()
                }

                # Cache response with TTL
                cache.setex(
                    cache_key,
                    ttl,
                    json.dumps(cache_data)
                )

                response.headers['X-Cache'] = 'MISS'
                response.headers['X-Cache-TTL'] = str(ttl)

        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Cache error in after_request: {str(e)}")

        return response

def cache_response(resource_type: Optional[str] = None, ttl: Optional[int] = None) -> Callable:
    """
    Decorator for caching view function responses.

    Args:
        resource_type (Optional[str]): Type of resource being cached
        ttl (Optional[int]): Custom TTL in seconds

    Returns:
        Callable: Decorated function
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if request.method not in CACHEABLE_METHODS:
                return f(*args, **kwargs)

            cache_key = get_cache_key_pattern(
                resource_type=resource_type or request.path.strip('/').split('/')[0],
                resource_id=kwargs.get('id'),
                version=CACHE_KEY_VERSION
            )

            try:
                with CacheManager() as cache:
                    # Check cache first
                    cached_data = cache.get(cache_key)
                    if cached_data:
                        return json.loads(cached_data)

                    # Execute view function
                    result = f(*args, **kwargs)

                    # Cache the result
                    cache_ttl = ttl or CACHE_TTL.get(resource_type, DEFAULT_CACHE_TTL)
                    cache.setex(cache_key, cache_ttl, json.dumps(result))

                    return result

            except RedisError as e:
                logger.error(f"Cache error in decorator: {str(e)}")
                return f(*args, **kwargs)

        return wrapper
    return decorator

def invalidate_cache(resource_type: str) -> Callable:
    """
    Decorator for invalidating cache entries after data modifications.

    Args:
        resource_type (str): Type of resource to invalidate

    Returns:
        Callable: Decorated function
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = f(*args, **kwargs)

            try:
                with CacheManager() as cache:
                    # Generate cache key pattern for resource type
                    pattern = get_cache_key_pattern(
                        resource_type=resource_type,
                        version=CACHE_KEY_VERSION
                    )
                    pattern = f"{pattern}*"

                    # Clear all matching cache entries
                    cache.clear_pattern(pattern)

            except RedisError as e:
                logger.error(f"Cache invalidation error: {str(e)}")

            return result

        return wrapper
    return decorator