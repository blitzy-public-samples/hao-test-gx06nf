"""
Rate limiting middleware for Flask applications with Redis-based storage.

This module implements request rate limiting functionality with:
- Redis-based counter storage with automatic expiration
- Configurable rate limits per user
- Prometheus metrics for monitoring
- Comprehensive error handling and retry logic
- Custom rate limit headers in responses

Version: 1.0
"""

from typing import Optional, Callable, Any, Tuple
import time
import functools
from flask import request, Response, g, current_app
from prometheus_client import Counter

from core.cache import get_redis_client
from config.security import SecurityConfig

# Global constants
RATE_LIMIT_KEY_PREFIX = 'rate_limit'
EXEMPT_PATHS = ['/health', '/metrics', '/ready']

# Prometheus metrics
RATE_LIMIT_METRICS = Counter(
    'rate_limit_hits_total',
    'Total number of rate limit hits',
    ['path', 'user_id']
)

class RateLimitMiddleware:
    """Flask middleware for request rate limiting with Redis storage and monitoring."""

    def __init__(self, app: Any) -> None:
        """
        Initialize rate limit middleware with Redis client and metrics.

        Args:
            app: Flask application instance
        """
        self._app = app
        self._redis_client = get_redis_client()
        self._rate_limit_counter = RATE_LIMIT_METRICS

        # Register middleware handlers
        app.before_request(self.before_request)
        app.after_request(self.after_request)

    def before_request(self) -> Optional[Response]:
        """
        Pre-request handler to check rate limits.

        Returns:
            Optional[Response]: 429 response if rate limit exceeded, None otherwise
        """
        # Skip rate limiting for exempt paths
        if request.path in EXEMPT_PATHS:
            return None

        # Get user identifier from request context
        user_id = getattr(g, 'user_id', request.remote_addr)

        # Check rate limit status
        is_limited, current_count = self.is_rate_limited(user_id)

        # Update metrics
        self._rate_limit_counter.labels(
            path=request.path,
            user_id=user_id
        ).inc()

        if is_limited:
            response = Response(
                '{"error": "Rate limit exceeded"}',
                status=429,
                mimetype='application/json'
            )
            self._add_rate_limit_headers(response, current_count)
            return response

        # Increment counter in Redis
        try:
            with self._redis_client.pipeline() as pipe:
                pipe.multi()
                key = get_rate_limit_key(user_id)
                pipe.incr(key)
                pipe.expire(key, SecurityConfig.RATE_LIMIT_PER_HOUR)
                pipe.execute()
        except Exception as e:
            current_app.logger.error(f"Redis error in rate limiting: {str(e)}")
            # Allow request through on Redis errors to maintain availability
            return None

        return None

    def after_request(self, response: Response) -> Response:
        """
        Post-request handler to add rate limit headers.

        Args:
            response: Flask response object

        Returns:
            Response: Modified response with rate limit headers
        """
        if request.path in EXEMPT_PATHS:
            return response

        user_id = getattr(g, 'user_id', request.remote_addr)
        try:
            current_count = int(self._redis_client.get(
                get_rate_limit_key(user_id)
            ) or 0)
            self._add_rate_limit_headers(response, current_count)
        except Exception as e:
            current_app.logger.error(f"Redis error in after_request: {str(e)}")

        return response

    def is_rate_limited(self, user_id: str) -> Tuple[bool, int]:
        """
        Check if request should be rate limited with retries.

        Args:
            user_id: User identifier for rate limiting

        Returns:
            Tuple[bool, int]: Rate limit status and current count
        """
        retry_count = 3
        while retry_count > 0:
            try:
                key = get_rate_limit_key(user_id)
                current_count = int(self._redis_client.get(key) or 0)
                return (
                    current_count >= SecurityConfig.RATE_LIMIT_PER_HOUR,
                    current_count
                )
            except Exception as e:
                current_app.logger.error(f"Redis retry {retry_count}: {str(e)}")
                retry_count -= 1
                if retry_count > 0:
                    time.sleep(0.1)  # Short delay between retries

        # Default to allowing request on persistent Redis errors
        return False, 0

    def _add_rate_limit_headers(self, response: Response, current_count: int) -> None:
        """
        Add rate limit headers to response.

        Args:
            response: Flask response object
            current_count: Current request count
        """
        limit = SecurityConfig.RATE_LIMIT_PER_HOUR
        remaining = max(0, limit - current_count)
        reset = int(time.time() + 3600)  # Reset after 1 hour

        response.headers.update({
            'X-RateLimit-Limit': str(limit),
            'X-RateLimit-Remaining': str(remaining),
            'X-RateLimit-Reset': str(reset)
        })


def get_rate_limit_key(user_id: str) -> str:
    """
    Generate Redis key for rate limiting with time window.

    Args:
        user_id: User identifier

    Returns:
        str: Formatted Redis key
    """
    # Use hourly time buckets for rate limiting
    time_bucket = int(time.time() / 3600)
    return f"{RATE_LIMIT_KEY_PREFIX}:{user_id}:{time_bucket}"


def rate_limit(limit_per_hour: Optional[int] = None) -> Callable:
    """
    Decorator for applying custom rate limits to routes.

    Args:
        limit_per_hour: Optional custom rate limit per hour

    Returns:
        Callable: Decorated function
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            user_id = getattr(g, 'user_id', request.remote_addr)
            redis_client = get_redis_client()
            
            # Use custom limit if provided, otherwise use default
            rate_limit = limit_per_hour or SecurityConfig.RATE_LIMIT_PER_HOUR
            
            try:
                key = get_rate_limit_key(user_id)
                current_count = int(redis_client.get(key) or 0)
                
                if current_count >= rate_limit:
                    response = Response(
                        '{"error": "Rate limit exceeded"}',
                        status=429,
                        mimetype='application/json'
                    )
                    return response
                
                with redis_client.pipeline() as pipe:
                    pipe.multi()
                    pipe.incr(key)
                    pipe.expire(key, 3600)  # 1 hour expiry
                    pipe.execute()
                    
            except Exception as e:
                current_app.logger.error(f"Rate limit decorator error: {str(e)}")
                # Allow request through on Redis errors
                return f(*args, **kwargs)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator