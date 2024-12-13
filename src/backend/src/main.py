"""
Main application entry point that initializes and configures the Flask application with
comprehensive middleware, security controls, monitoring, and API routes.

This module:
- Initializes Flask application with production-ready configuration
- Sets up database connections and connection pooling
- Configures security middleware and authentication
- Implements monitoring and metrics collection
- Registers API routes and error handlers
- Manages application lifecycle

Version: 1.0.0
"""

import os
import atexit
import logging
import structlog
from typing import Optional

from flask import Flask, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

from api.routes import init_app
from config.settings import get_config
from core.database import DatabaseManager
from core.security import configure_security
from utils.constants import (
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    RATE_LIMIT_CONSTANTS
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# Initialize global objects
app = Flask(__name__)
db = DatabaseManager()
metrics = PrometheusMetrics(app)

def create_app(env_name: str) -> Flask:
    """
    Factory function that creates and configures the Flask application instance.

    Args:
        env_name: Environment name (development, production, testing)

    Returns:
        Flask: Configured Flask application instance
    """
    try:
        # Load environment-specific configuration
        config = get_config()
        app.config.from_object(config)

        # Configure security middleware
        configure_security(app)
        
        # Configure CORS
        CORS(app, resources={
            r"/api/*": {
                "origins": app.config['CORS_ORIGINS'],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
                "expose_headers": ["Content-Range", "X-Total-Count"],
                "supports_credentials": True,
                "max_age": 600
            }
        })

        # Configure rate limiting
        limiter = Limiter(
            app,
            key_func=get_remote_address,
            default_limits=[f"{RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR']}/hour"],
            storage_uri=app.config['RATE_LIMIT_CONFIG']['STORAGE_URL']
        )

        # Initialize database connection pool
        db.init_app(app)

        # Configure Prometheus metrics
        metrics.info("app_info", "Application info", version="1.0.0")
        
        # Register health check endpoint
        @app.route('/health')
        @metrics.do_not_track()
        def health_check():
            """Basic health check endpoint."""
            try:
                # Verify database connection
                db.get_session().execute("SELECT 1")
                return jsonify({
                    "status": "healthy",
                    "components": {
                        "database": "connected",
                        "api": "running"
                    }
                }), HTTP_STATUS_CODES['OK']
            except Exception as e:
                logger.error("Health check failed", error=str(e))
                return jsonify({
                    "status": "unhealthy",
                    "error": str(e)
                }), HTTP_STATUS_CODES['SERVICE_UNAVAILABLE']

        # Initialize routes and blueprints
        init_app(app)

        # Configure error handlers
        configure_error_handlers(app)

        logger.info(
            "Application initialized successfully",
            environment=env_name
        )
        return app

    except Exception as e:
        logger.error(
            "Failed to initialize application",
            error=str(e),
            environment=env_name
        )
        raise

def configure_error_handlers(app: Flask) -> None:
    """
    Configure application-wide error handlers with logging and monitoring.

    Args:
        app: Flask application instance
    """
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle resource not found errors."""
        logger.warning(
            "Resource not found",
            path=request.path,
            method=request.method
        )
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": ERROR_MESSAGES['RESOURCE_NOT_FOUND']
            }
        }), HTTP_STATUS_CODES['NOT_FOUND']

    @app.errorhandler(500)
    def handle_server_error(error):
        """Handle internal server errors."""
        logger.error(
            "Internal server error",
            error=str(error),
            path=request.path,
            method=request.method
        )
        return jsonify({
            "error": {
                "code": "SERVER_ERROR",
                "message": ERROR_MESSAGES['SERVER_ERROR']
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

    @app.errorhandler(429)
    def handle_rate_limit(error):
        """Handle rate limit exceeded errors."""
        logger.warning(
            "Rate limit exceeded",
            path=request.path,
            method=request.method
        )
        return jsonify({
            "error": {
                "code": "RATE_LIMITED",
                "message": ERROR_MESSAGES['RATE_LIMIT_EXCEEDED']
            }
        }), HTTP_STATUS_CODES['RATE_LIMITED']

@atexit.register
def cleanup():
    """Cleanup function to handle application shutdown."""
    try:
        # Export final metrics
        metrics.export_defaults()
        
        # Close database connections
        db.close_connections()
        
        logger.info("Application shutdown completed successfully")
    except Exception as e:
        logger.error("Error during application shutdown", error=str(e))

if __name__ == '__main__':
    # Get environment from environment variable
    env = os.getenv('FLASK_ENV', 'development')
    
    # Create and run application
    app = create_app(env)
    
    # Run with appropriate settings
    debug = env == 'development'
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 8000)),
        debug=debug
    )