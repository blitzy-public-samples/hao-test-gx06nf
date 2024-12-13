"""
Utility decorators module providing reusable function and method decorators for
authentication, caching, rate limiting, and error handling across the application.

This module implements production-ready decorators with enhanced Redis integration
and robust error handling for securing and optimizing API endpoints.

Version: 1.0
"""

import functools
import time
from typing import Callable, Dict, Any, Optional
from datetime import datetime

import redis  # version: 4.0+
from flask import request, current_app, g, Response, jsonify  # version: 2.0+

from api.auth.utils import (
    verify_token,
    AuthUtils,
    extract_token,
    is_token_blacklisted
)
from utils.constants import (
    RATE_LIMIT_CONSTANTS,
    CACHE_CONSTANTS,
    HTTP_STATUS_CODES,
    ERROR_MESSAGES
)

# Initialize Redis client for rate limiting and caching
redis_client = redis.Redis(
    host=current_app.config.get('REDIS_HOST', 'localhost'),
    port=current_app.config.get('REDIS_PORT', 6379),
    decode_responses=True
)

def require_auth(func: Callable) -> Callable:
    """
    Enhanced decorator that requires valid JWT authentication for endpoint access.
    Implements token refresh, context enrichment, and comprehensive error handling.

    Args:
        func (Callable): The function to wrap with authentication

    Returns:
        Callable: Wrapped function with authentication checks
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            # Extract token from Authorization header
            auth_header = request.headers.get('Authorization')
            token = extract_token(auth_header)

            # Verify token is not blacklisted
            if is_token_blacklisted(token):
                return jsonify({
                    'error': ERROR_MESSAGES['UNAUTHORIZED_ACCESS'],
                    'status': 'error'
                }), HTTP_STATUS_CODES['UNAUTHORIZED']

            # Verify and decode token
            payload = verify_token(token)

            # Check if token needs refresh (within 5 minutes of expiry)
            exp_timestamp = payload.get('exp', 0)
            current_time = datetime.utcnow().timestamp()
            if exp_timestamp - current_time < 300:  # 5 minutes
                # Attempt token refresh
                auth_utils = AuthUtils()
                new_token = auth_utils.refresh_token(token)
                g.refreshed_token = new_token

            # Add user context to request
            g.user_id = payload.get('sub')
            g.user_permissions = payload.get('permissions', [])

            # Execute wrapped function
            response = func(*args, **kwargs)

            # Add authentication headers if needed
            if isinstance(response, tuple):
                response_obj, status_code = response
                headers = {}
                if hasattr(g, 'refreshed_token'):
                    headers['X-Refreshed-Token'] = g.refreshed_token
                return response_obj, status_code, headers
            return response

        except Exception as e:
            current_app.logger.error(f"Authentication error: {str(e)}")
            return jsonify({
                'error': str(e),
                'status': 'error'
            }), HTTP_STATUS_CODES['UNAUTHORIZED']

    return wrapper

def rate_limit(func: Callable) -> Callable:
    """
    Sliding window rate limiting decorator with burst protection and header information.
    Implements Redis-backed rate tracking with configurable limits and windows.

    Args:
        func (Callable): The function to wrap with rate limiting

    Returns:
        Callable: Wrapped function with rate limiting
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            # Get user ID from context
            user_id = getattr(g, 'user_id', 'anonymous')
            
            # Generate rate limit key
            window = int(time.time() // RATE_LIMIT_CONSTANTS['RATE_LIMIT_WINDOW_SECONDS'])
            rate_key = f"rate_limit:{user_id}:{window}"
            
            # Check current request count
            pipe = redis_client.pipeline()
            pipe.incr(rate_key)
            pipe.expire(rate_key, RATE_LIMIT_CONSTANTS['RATE_LIMIT_WINDOW_SECONDS'])
            current_requests = pipe.execute()[0]

            # Check burst limit
            burst_key = f"burst_limit:{user_id}"
            current_burst = redis_client.get(burst_key) or 0
            
            # Verify rate limits
            if (current_requests > RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR'] or
                int(current_burst) > RATE_LIMIT_CONSTANTS['BURST_LIMIT']):
                
                retry_after = RATE_LIMIT_CONSTANTS['RATE_LIMIT_WINDOW_SECONDS']
                response = jsonify({
                    'error': ERROR_MESSAGES['RATE_LIMIT_EXCEEDED'],
                    'status': 'error'
                })
                
                response.headers.update({
                    'X-RateLimit-Limit': str(RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR']),
                    'X-RateLimit-Remaining': '0',
                    'X-RateLimit-Reset': str(int(time.time()) + retry_after),
                    'Retry-After': str(retry_after)
                })
                
                return response, HTTP_STATUS_CODES['RATE_LIMITED']

            # Update burst tracking
            redis_client.setex(
                burst_key,
                1,  # 1 second expiry for burst window
                int(current_burst) + 1
            )

            # Execute wrapped function
            response = func(*args, **kwargs)

            # Add rate limit headers
            if isinstance(response, tuple):
                response_obj, status_code = response
                headers = {
                    'X-RateLimit-Limit': str(RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR']),
                    'X-RateLimit-Remaining': str(
                        RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR'] - current_requests
                    ),
                    'X-RateLimit-Reset': str(
                        int(time.time()) + RATE_LIMIT_CONSTANTS['RATE_LIMIT_WINDOW_SECONDS']
                    )
                }
                return response_obj, status_code, headers
            return response

        except redis.RedisError as e:
            current_app.logger.error(f"Rate limiting error: {str(e)}")
            # Fail open to prevent system lockout
            return func(*args, **kwargs)

    return wrapper

def cache_response(ttl: Optional[int] = None) -> Callable:
    """
    Intelligent response caching decorator with dynamic TTL and method-specific behavior.
    Implements Redis-backed caching with automatic invalidation and compression.

    Args:
        ttl (Optional[int]): Cache TTL in seconds, defaults to specification type TTL

    Returns:
        Callable: Wrapped function with caching behavior
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Skip caching for non-GET methods
            if request.method != 'GET':
                return func(*args, **kwargs)

            try:
                # Generate cache key
                cache_key = f"{CACHE_CONSTANTS['CACHE_KEY_PREFIX']}:{request.path}"
                if request.query_string:
                    cache_key += f":{request.query_string.decode()}"
                if hasattr(g, 'user_id'):
                    cache_key += f":{g.user_id}"

                # Determine TTL based on endpoint type
                cache_ttl = ttl
                if cache_ttl is None:
                    if 'projects' in request.path:
                        cache_ttl = CACHE_CONSTANTS['PROJECT_CACHE_TTL']
                    elif 'specifications' in request.path:
                        cache_ttl = CACHE_CONSTANTS['SPECIFICATION_CACHE_TTL']
                    elif 'items' in request.path:
                        cache_ttl = CACHE_CONSTANTS['ITEMS_CACHE_TTL']
                    else:
                        cache_ttl = CACHE_CONSTANTS['PROJECT_CACHE_TTL']

                # Check cache
                cached_response = redis_client.get(cache_key)
                if cached_response:
                    return jsonify(eval(cached_response))

                # Execute function and cache response
                response = func(*args, **kwargs)
                
                if isinstance(response, tuple):
                    response_data, status_code = response
                    if status_code == HTTP_STATUS_CODES['OK']:
                        redis_client.setex(
                            cache_key,
                            cache_ttl,
                            str(response_data)
                        )
                    return response_data, status_code
                
                # Cache successful responses
                redis_client.setex(
                    cache_key,
                    cache_ttl,
                    str(response)
                )
                return response

            except redis.RedisError as e:
                current_app.logger.error(f"Caching error: {str(e)}")
                # Fail open on cache errors
                return func(*args, **kwargs)

        return wrapper
    return decorator

__all__ = [
    'require_auth',
    'rate_limit',
    'cache_response'
]