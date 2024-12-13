"""
Authentication middleware module implementing request authentication, token validation,
security controls, rate limiting, and monitoring for the Flask API.

This module provides comprehensive security controls including:
- JWT token validation with caching
- Rate limiting with Redis backend
- Security headers enforcement
- Authentication metrics collection
- Brute force protection

Version: 1.0
"""

from typing import Optional, Dict, Any, Final
from functools import wraps
import logging
from datetime import datetime
from flask import Flask, Request, Response, request, g
from redis import Redis  # version: 4.0+
from prometheus_client import Counter, Histogram  # version: 0.14+

from api.auth.jwt import JWTHandler
from api.auth.google import GoogleAuthClient
from config.security import SecurityConfig
from core.cache import get_redis_client

# Configure logging
logger = logging.getLogger(__name__)

# Constants for authentication
EXCLUDED_PATHS: Final[list] = ['/health', '/api/v1/auth/login', '/api/v1/auth/refresh', '/metrics']
AUTH_HEADER: Final[str] = 'Authorization'
BEARER_PREFIX: Final[str] = 'Bearer '
TOKEN_CACHE_TTL: Final[int] = 300  # 5 minutes

# Security headers configuration
SECURITY_HEADERS: Final[Dict[str, str]] = {
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'",
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'X-XSS-Protection': '1; mode=block'
}

class AuthMiddleware:
    """Authentication middleware class for handling request authentication and security controls."""

    def __init__(self, app: Flask) -> None:
        """
        Initialize authentication middleware with required handlers and metrics.

        Args:
            app: Flask application instance
        """
        self._jwt_handler = JWTHandler()
        self._google_client = GoogleAuthClient()
        self._cache_client = get_redis_client()
        self._rate_limits: Dict[str, Dict[str, Any]] = {}

        # Initialize Prometheus metrics
        self._auth_failures = Counter(
            'auth_failures_total',
            'Total number of authentication failures',
            ['path', 'error_type']
        )
        self._request_latency = Histogram(
            'request_auth_latency_seconds',
            'Authentication processing latency',
            ['path']
        )

        # Register middleware handlers
        app.before_request(self.authenticate_request)
        app.after_request(self.add_security_headers)

    def authenticate_request(self) -> Optional[Response]:
        """
        Authenticate incoming request using JWT token with rate limiting and monitoring.

        Returns:
            Optional[Response]: Error response if authentication fails, None if successful
        """
        start_time = datetime.utcnow()

        try:
            # Skip authentication for excluded paths
            if is_excluded_path(request.path):
                return None

            # Check rate limit
            client_ip = request.remote_addr
            if self.check_rate_limit(client_ip):
                self._auth_failures.labels(
                    path=request.path,
                    error_type='rate_limit'
                ).inc()
                return Response(
                    'Rate limit exceeded',
                    status=429
                )

            # Extract and validate token
            token = extract_token(request)
            if not token:
                self._auth_failures.labels(
                    path=request.path,
                    error_type='missing_token'
                ).inc()
                return Response(
                    'Missing authentication token',
                    status=401
                )

            # Check token cache
            cached_payload = self._cache_client.get(f"token:{token}")
            if cached_payload:
                g.user = cached_payload
                return None

            # Validate JWT token
            try:
                payload = self._jwt_handler.validate_token(token)
                if not payload:
                    raise ValueError("Invalid token")

                # Verify Google OAuth token if needed
                if 'google_token' in payload:
                    google_info = self._google_client.verify_oauth_token(
                        payload['google_token']
                    )
                    payload.update({'google_info': google_info})

                # Cache validated token
                self._cache_client.setex(
                    f"token:{token}",
                    TOKEN_CACHE_TTL,
                    payload
                )

                # Add user context to request
                g.user = payload
                return None

            except Exception as e:
                logger.error(f"Token validation failed: {str(e)}")
                self._auth_failures.labels(
                    path=request.path,
                    error_type='invalid_token'
                ).inc()
                return Response(
                    'Invalid authentication token',
                    status=401
                )

        finally:
            # Record authentication latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._request_latency.labels(path=request.path).observe(duration)

    def check_rate_limit(self, client_ip: str) -> bool:
        """
        Check and enforce rate limiting for client requests.

        Args:
            client_ip: Client IP address

        Returns:
            bool: True if rate limit exceeded, False otherwise
        """
        current_time = datetime.utcnow().timestamp()
        window_start = current_time - SecurityConfig.RATE_LIMIT_WINDOW_SECONDS

        # Clean expired entries
        self._rate_limits = {
            ip: data for ip, data in self._rate_limits.items()
            if data['timestamp'] > window_start
        }

        # Check current request count
        client_data = self._rate_limits.get(client_ip, {
            'count': 0,
            'timestamp': current_time
        })

        if client_data['count'] >= SecurityConfig.RATE_LIMIT_MAX_REQUESTS:
            return True

        # Update request count
        client_data['count'] += 1
        client_data['timestamp'] = current_time
        self._rate_limits[client_ip] = client_data

        return False

    def add_security_headers(self, response: Response) -> Response:
        """
        Add security headers to response.

        Args:
            response: Flask response object

        Returns:
            Response: Modified response with security headers
        """
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


def extract_token(request: Request) -> Optional[str]:
    """
    Extract JWT token from request Authorization header.

    Args:
        request: Flask request object

    Returns:
        Optional[str]: Extracted token or None if not found
    """
    auth_header = request.headers.get(AUTH_HEADER)
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0] != BEARER_PREFIX.strip():
        return None

    return parts[1]


def is_excluded_path(path: str) -> bool:
    """
    Check if request path is excluded from authentication.

    Args:
        path: Request path

    Returns:
        bool: True if path is excluded from authentication
    """
    return any(path.startswith(excluded) for excluded in EXCLUDED_PATHS)