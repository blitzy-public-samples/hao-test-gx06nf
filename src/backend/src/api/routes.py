"""
Main Flask application routing configuration implementing secure API endpoints,
middleware, monitoring, and error handling with comprehensive security controls.

This module:
- Registers all API blueprints with proper versioning
- Configures global security middleware and CORS
- Implements request monitoring and metrics
- Sets up comprehensive error handling
- Configures performance optimization

Version: 1.0.0
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from prometheus_flask_exporter import PrometheusMetrics

from .endpoints.health import health_bp
from .endpoints.users import users_bp
from .endpoints.projects import projects_router
from .endpoints.specifications import specifications_bp
from utils.constants import (
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    RATE_LIMIT_CONSTANTS
)

# Configure logging
logger = logging.getLogger(__name__)

def init_app(app: Flask) -> Flask:
    """
    Initialize Flask application with comprehensive security controls,
    monitoring, and routing configuration.

    Args:
        app: Flask application instance

    Returns:
        Flask: Configured Flask application
    """
    # Configure CORS with security settings
    CORS(app, resources={
        r"/api/*": {
            "origins": ["https://app.example.com"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Range", "X-Total-Count"],
            "supports_credentials": True,
            "max_age": 600
        }
    })

    # Initialize Prometheus metrics
    metrics = PrometheusMetrics(app)
    metrics.info("app_info", "Application info", version="1.0.0")

    # Configure rate limiting
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        default_limits=[f"{RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR']}/hour"],
        storage_uri="redis://localhost:6379/0"
    )

    # Configure security headers with Talisman
    Talisman(
        app,
        force_https=True,
        strict_transport_security=True,
        session_cookie_secure=True,
        content_security_policy={
            'default-src': "'self'",
            'img-src': "'self' data:",
            'script-src': "'self'",
            'style-src': "'self'"
        }
    )

    # Register blueprints
    app.register_blueprint(health_bp, url_prefix='/health')
    app.register_blueprint(users_bp, url_prefix='/api/v1/users')
    app.register_blueprint(projects_router, url_prefix='/api/v1/projects')
    app.register_blueprint(specifications_bp, url_prefix='/api/v1/specifications')

    # Register error handlers
    register_error_handlers(app)

    # Configure request monitoring
    setup_monitoring(app)

    return app

def register_error_handlers(app: Flask) -> None:
    """
    Register comprehensive error handlers for consistent error responses
    and monitoring.

    Args:
        app: Flask application instance
    """
    @app.errorhandler(400)
    def handle_bad_request(error: Any) -> Tuple[Dict[str, Any], int]:
        """Handle validation errors."""
        logger.warning(
            f"Bad request: {str(error)}",
            extra={"path": request.path, "method": request.method}
        )
        return jsonify({
            "error": {
                "code": "INVALID_REQUEST",
                "message": str(error),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    @app.errorhandler(401)
    def handle_unauthorized(error: Any) -> Tuple[Dict[str, Any], int]:
        """Handle authentication failures."""
        logger.warning(
            f"Unauthorized access: {str(error)}",
            extra={"path": request.path, "method": request.method}
        )
        return jsonify({
            "error": {
                "code": "UNAUTHORIZED",
                "message": ERROR_MESSAGES['UNAUTHORIZED_ACCESS'],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['UNAUTHORIZED']

    @app.errorhandler(403)
    def handle_forbidden(error: Any) -> Tuple[Dict[str, Any], int]:
        """Handle authorization failures."""
        logger.warning(
            f"Forbidden access: {str(error)}",
            extra={"path": request.path, "method": request.method}
        )
        return jsonify({
            "error": {
                "code": "FORBIDDEN",
                "message": ERROR_MESSAGES['PROJECT_ACCESS_DENIED'],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['FORBIDDEN']

    @app.errorhandler(404)
    def handle_not_found(error: Any) -> Tuple[Dict[str, Any], int]:
        """Handle resource not found errors."""
        logger.info(
            f"Resource not found: {request.path}",
            extra={"method": request.method}
        )
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": ERROR_MESSAGES['RESOURCE_NOT_FOUND'],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['NOT_FOUND']

    @app.errorhandler(429)
    def handle_rate_limit(error: Any) -> Tuple[Dict[str, Any], int]:
        """Handle rate limit exceeded errors."""
        logger.warning(
            f"Rate limit exceeded: {str(error)}",
            extra={"path": request.path, "method": request.method}
        )
        return jsonify({
            "error": {
                "code": "RATE_LIMITED",
                "message": ERROR_MESSAGES['RATE_LIMIT_EXCEEDED'],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['RATE_LIMITED']

    @app.errorhandler(500)
    def handle_server_error(error: Any) -> Tuple[Dict[str, Any], int]:
        """Handle internal server errors."""
        logger.error(
            f"Internal server error: {str(error)}",
            extra={"path": request.path, "method": request.method},
            exc_info=True
        )
        return jsonify({
            "error": {
                "code": "SERVER_ERROR",
                "message": "An unexpected error occurred",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

def setup_monitoring(app: Flask) -> None:
    """
    Configure request monitoring and performance tracking.

    Args:
        app: Flask application instance
    """
    @app.before_request
    def before_request() -> None:
        """Record request start time."""
        request.start_time = datetime.now(timezone.utc)

    @app.after_request
    def after_request(response: Any) -> Any:
        """
        Log request completion and calculate duration.
        
        Args:
            response: Flask response object
            
        Returns:
            Response object with added headers
        """
        duration = (datetime.now(timezone.utc) - request.start_time).total_seconds()
        
        # Add response headers
        response.headers['X-Request-ID'] = request.id
        response.headers['X-Response-Time'] = str(duration)
        
        # Log request details
        logger.info(
            "Request completed",
            extra={
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration": duration,
                "user_id": getattr(request, 'user_id', None)
            }
        )
        
        return response

# Export initialization function
__all__ = ['init_app']