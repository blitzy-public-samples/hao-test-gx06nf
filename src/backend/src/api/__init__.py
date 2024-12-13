"""
Flask application factory module that initializes and configures the REST API application
with comprehensive middleware, error handlers, and route blueprints.

This module implements:
- Application factory pattern with environment-specific configuration
- Security middleware with JWT and Google Auth
- Request logging and correlation IDs
- Redis-based response caching
- Rate limiting controls
- Error handling with standardized responses
- API route registration with versioning

Version: 1.0.0
"""

import logging
from typing import Optional
from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from circuitbreaker import CircuitBreaker

from config.settings import get_config
from api.middleware.security import SecurityMiddleware
from api.middleware.logging import RequestLoggingMiddleware
from api.middleware.cache import CacheMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.errors.handlers import error_handlers
from api.routes import init_app as init_routes

# Configure logging
logger = logging.getLogger(__name__)

def create_app(config_name: str) -> Flask:
    """
    Factory function to create and configure Flask application instance with
    comprehensive security, monitoring, and performance features.

    Args:
        config_name: Environment configuration name (development/staging/production)

    Returns:
        Flask: Configured Flask application instance
    """
    try:
        # Create Flask app instance
        app = Flask(__name__)

        # Load configuration
        config = get_config()
        app.config.from_object(config)

        # Configure proxy settings
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_port=1,
            x_prefix=1
        )

        # Initialize CORS with security settings
        CORS(app, resources={
            r"/api/*": {
                "origins": app.config.get('CORS_ORIGINS', []),
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
                "expose_headers": ["Content-Range", "X-Total-Count"],
                "supports_credentials": True,
                "max_age": 600
            }
        })

        # Configure request timeout
        app.config['TIMEOUT'] = 30  # 30 second timeout

        # Configure circuit breaker for external services
        circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=Exception
        )

        # Register middleware
        SecurityMiddleware(app)  # Security controls and JWT validation
        RequestLoggingMiddleware(app)  # Request logging and correlation IDs
        CacheMiddleware(app)  # Redis response caching
        RateLimitMiddleware(app)  # Request rate limiting

        # Configure security headers
        @app.after_request
        def add_security_headers(response):
            """Add security headers to all responses."""
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Content-Security-Policy'] = "default-src 'self'"
            return response

        # Register error handlers
        app.register_blueprint(error_handlers)

        # Register API routes with versioning
        init_routes(app)

        # Log successful initialization
        logger.info(
            "Application initialized successfully",
            extra={
                "environment": config_name,
                "debug": app.debug
            }
        )

        return app

    except Exception as e:
        logger.error(
            f"Failed to initialize application: {str(e)}",
            extra={"config_name": config_name},
            exc_info=True
        )
        raise

__all__ = ['create_app']