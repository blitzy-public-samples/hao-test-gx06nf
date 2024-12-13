"""
Middleware initialization module for Flask application.

This module initializes and configures all middleware components including:
- Security middleware for HTTPS, CORS and security headers
- Logging middleware for request tracking and monitoring
- Cache middleware for Redis-based response caching
- Rate limiting middleware for request frequency control

Version: 1.0
"""

from typing import Optional
from flask import Flask

from api.middleware.security import SecurityMiddleware
from api.middleware.logging import RequestLoggingMiddleware
from api.middleware.cache import CacheMiddleware
from api.middleware.rate_limit import RateLimitMiddleware, rate_limit, RateLimitExceeded

def init_middleware(app: Flask) -> None:
    """
    Initialize and configure all middleware components with comprehensive error handling.

    Args:
        app (Flask): Flask application instance

    Raises:
        ValueError: If Flask app instance is invalid
        RuntimeError: If middleware initialization fails
    """
    if not isinstance(app, Flask):
        raise ValueError("Invalid Flask application instance")

    try:
        # Initialize security middleware with HTTPS and CORS
        security_middleware = SecurityMiddleware(app)
        app.before_request(security_middleware.before_request)
        app.after_request(security_middleware.after_request)

        # Setup logging middleware with cloud integration
        logging_middleware = RequestLoggingMiddleware(app)
        app.wsgi_app = logging_middleware(app.wsgi_app)

        # Configure cache middleware with Redis
        cache_middleware = CacheMiddleware(app)
        app.before_request(cache_middleware.before_request)
        app.after_request(cache_middleware.after_request)

        # Initialize rate limiting middleware
        rate_limit_middleware = RateLimitMiddleware(app)
        app.before_request(rate_limit_middleware.before_request)
        app.after_request(rate_limit_middleware.after_request)

        # Register error handlers
        @app.errorhandler(RateLimitExceeded)
        def handle_rate_limit_error(error):
            return {
                'error': 'Rate limit exceeded',
                'message': str(error)
            }, 429

        # Register health check endpoint
        @app.route('/health')
        def health_check():
            """Health check endpoint for monitoring."""
            return {'status': 'healthy'}, 200

        app.logger.info("All middleware components initialized successfully")

    except Exception as e:
        app.logger.error(f"Failed to initialize middleware: {str(e)}")
        raise RuntimeError(f"Middleware initialization failed: {str(e)}")

# Export middleware components and utilities
__all__ = [
    'SecurityMiddleware',
    'RequestLoggingMiddleware', 
    'CacheMiddleware',
    'RateLimitMiddleware',
    'rate_limit',
    'RateLimitExceeded',
    'init_middleware'
]