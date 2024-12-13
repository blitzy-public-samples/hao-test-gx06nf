"""
Security middleware module implementing comprehensive HTTP security headers,
request validation, rate limiting, and security controls for the Flask application.

This module provides:
- Security header injection
- Request validation
- Rate limiting
- Origin validation
- Token validation
- Request size limits
- Secure cookie configuration

Version: 1.0
"""

from functools import wraps  # version 3.8+
from flask import Flask, request, Response, g  # version 2.0+
from typing import Callable, Dict, Optional, Union  # version 3.8+
import secrets  # version 3.8+
import time
from datetime import datetime

from config.security import SecurityConfig
from core.security import SecurityManager
from utils.constants import (
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    RATE_LIMIT_CONSTANTS
)

# Global security configuration
SECURE_HEADERS: Dict[str, str] = SecurityConfig.SECURITY_HEADERS
RATE_LIMIT: Dict[str, int] = {
    'requests_per_hour': RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR'],
    'window_seconds': RATE_LIMIT_CONSTANTS['RATE_LIMIT_WINDOW_SECONDS'],
    'burst_limit': RATE_LIMIT_CONSTANTS['BURST_LIMIT']
}

class SecurityMiddleware:
    """
    Comprehensive security middleware implementing request validation,
    header injection, and protection measures.
    """

    def __init__(self, app: Flask):
        """
        Initialize security middleware with Flask application.

        Args:
            app (Flask): Flask application instance
        """
        self._app = app
        self._security_manager = SecurityManager()
        self._rate_limits: Dict[str, Dict[str, Union[int, float]]] = {}

        # Register middleware handlers
        self._app.before_request(self.before_request)
        self._app.after_request(self.after_request)

        # Configure secure session
        self._configure_secure_session()

    def _configure_secure_session(self) -> None:
        """Configure secure session cookie settings."""
        self._app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Strict',
            PERMANENT_SESSION_LIFETIME=86400  # 24 hours
        )

    def before_request(self) -> Optional[Response]:
        """
        Comprehensive request validation handler.

        Returns:
            Optional[Response]: Error response if request is invalid, None if valid
        """
        # Verify HTTPS in production
        if self._app.env == 'production' and not request.is_secure:
            return Response(
                'HTTPS Required',
                status=HTTP_STATUS_CODES['BAD_REQUEST']
            )

        # Validate request headers
        if not self._validate_headers():
            return Response(
                'Invalid Headers',
                status=HTTP_STATUS_CODES['BAD_REQUEST']
            )

        # Check token blacklist
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if auth_token and self._security_manager.is_token_blacklisted(auth_token):
            return Response(
                ERROR_MESSAGES['INVALID_TOKEN'],
                status=HTTP_STATUS_CODES['UNAUTHORIZED']
            )

        # Check rate limits
        if not self._check_rate_limit():
            return Response(
                ERROR_MESSAGES['RATE_LIMIT_EXCEEDED'],
                status=HTTP_STATUS_CODES['RATE_LIMITED']
            )

        # Validate request size
        if request.content_length and request.content_length > 10 * 1024 * 1024:  # 10MB
            return Response(
                'Request Too Large',
                status=HTTP_STATUS_CODES['BAD_REQUEST']
            )

        return None

    def after_request(self, response: Response) -> Response:
        """
        Response modification handler for security measures.

        Args:
            response (Response): Flask response object

        Returns:
            Response: Modified response with security enhancements
        """
        # Generate CSP nonce
        nonce = secrets.token_urlsafe(16)
        g.csp_nonce = nonce

        # Apply base security headers
        for header, value in SECURE_HEADERS.items():
            response.headers[header] = value

        # Add CSP with nonce
        csp = SECURE_HEADERS['Content-Security-Policy']
        response.headers['Content-Security-Policy'] = (
            f"{csp} 'nonce-{nonce}'"
        )

        # Add HSTS in production
        if self._app.env == 'production':
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )

        return response

    def _validate_headers(self) -> bool:
        """
        Validate request headers for security requirements.

        Returns:
            bool: True if headers are valid, False otherwise
        """
        # Check content type for POST/PUT requests
        if request.method in ['POST', 'PUT']:
            content_type = request.headers.get('Content-Type', '')
            if not content_type.startswith('application/json'):
                return False

        # Validate origin for CORS requests
        origin = request.headers.get('Origin')
        if origin and not self._validate_origin(origin):
            return False

        return True

    def _validate_origin(self, origin: str) -> bool:
        """
        Validate request origin against allowed origins.

        Args:
            origin (str): Request origin

        Returns:
            bool: True if origin is valid, False otherwise
        """
        allowed_origins = self._app.config.get('ALLOWED_ORIGINS', [])
        return origin in allowed_origins if allowed_origins else True

    def _check_rate_limit(self) -> bool:
        """
        Check if request is within rate limits.

        Returns:
            bool: True if within limits, False otherwise
        """
        user_id = g.get('user_id', request.remote_addr)
        current_time = time.time()

        if user_id not in self._rate_limits:
            self._rate_limits[user_id] = {
                'count': 0,
                'window_start': current_time
            }

        user_limits = self._rate_limits[user_id]

        # Reset window if expired
        if current_time - user_limits['window_start'] > RATE_LIMIT['window_seconds']:
            user_limits.update({
                'count': 0,
                'window_start': current_time
            })

        # Check limits
        if user_limits['count'] >= RATE_LIMIT['requests_per_hour']:
            return False

        # Increment counter
        user_limits['count'] += 1
        return True

def apply_security_headers(f: Callable) -> Callable:
    """
    Decorator that applies comprehensive security headers to response.

    Args:
        f (Callable): Function to wrap

    Returns:
        Callable: Decorated function with enhanced security headers
    """
    @wraps(f)
    def decorated(*args, **kwargs) -> Response:
        response = f(*args, **kwargs)
        if isinstance(response, Response):
            # Generate nonce for CSP
            nonce = secrets.token_urlsafe(16)
            g.csp_nonce = nonce

            # Apply security headers
            for header, value in SECURE_HEADERS.items():
                response.headers[header] = value

            # Add CSP with nonce
            csp = SECURE_HEADERS['Content-Security-Policy']
            response.headers['Content-Security-Policy'] = f"{csp} 'nonce-{nonce}'"

        return response
    return decorated

def validate_secure_request(f: Callable) -> Callable:
    """
    Validates request for comprehensive security requirements.

    Args:
        f (Callable): Function to wrap

    Returns:
        Callable: Decorated function with request validation
    """
    @wraps(f)
    def decorated(*args, **kwargs) -> Union[Response, Callable]:
        # Verify HTTPS in production
        if Flask.current_app.env == 'production' and not request.is_secure:
            return Response(
                'HTTPS Required',
                status=HTTP_STATUS_CODES['BAD_REQUEST']
            )

        # Validate token
        auth_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if auth_token:
            security_manager = SecurityManager()
            if security_manager.is_token_blacklisted(auth_token):
                return Response(
                    ERROR_MESSAGES['INVALID_TOKEN'],
                    status=HTTP_STATUS_CODES['UNAUTHORIZED']
                )

        # Validate content type
        if request.method in ['POST', 'PUT']:
            if not request.is_json:
                return Response(
                    'Invalid Content-Type',
                    status=HTTP_STATUS_CODES['BAD_REQUEST']
                )

        return f(*args, **kwargs)
    return decorated