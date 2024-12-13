"""
Main package initializer implementing Flask application factory pattern with comprehensive
security, monitoring, and health check features.

This module:
- Configures the Flask application with environment-specific settings
- Initializes core components (database, cache, security)
- Sets up logging and monitoring
- Implements health checks and security headers
- Configures CORS and rate limiting

Version: 1.0.0
"""

import os
import logging
from typing import Optional
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_request_id import RequestId
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from prometheus_client import Counter, Histogram

from .api.routes import init_app
from .config.settings import get_config
from .utils.constants import (
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    RATE_LIMIT_CONSTANTS
)

# Configure logging
logger = logging.getLogger(__name__)

# Global constants
ENV = os.getenv('FLASK_ENV', 'development')
VERSION = os.getenv('APP_VERSION', '1.0.0')

# Request ID configuration
REQUEST_ID_CONFIG = {
    'REQUEST_ID_HEADER': 'X-Request-ID',
    'GENERATE_IF_NOT_FOUND': True
}

# Prometheus metrics
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

def create_app(env_name: Optional[str] = None) -> Flask:
    """
    Flask application factory implementing comprehensive security and monitoring.

    Args:
        env_name: Optional environment name override

    Returns:
        Flask: Configured Flask application instance
    """
    try:
        # Load configuration
        config_class = get_config()
        
        # Create Flask app
        app = Flask(__name__.split('.')[0])
        
        # Configure app
        app.config.from_object(config_class)
        app.secret_key = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
        
        # Initialize request ID tracking
        RequestId(app, **REQUEST_ID_CONFIG)
        
        # Configure logging
        configure_logging(env_name or ENV, app)
        
        # Initialize security headers
        Talisman(
            app,
            force_https=ENV == 'production',
            strict_transport_security=True,
            session_cookie_secure=ENV == 'production',
            content_security_policy={
                'default-src': "'self'",
                'img-src': "'self' data:",
                'script-src': "'self'",
                'style-src': "'self'"
            }
        )
        
        # Configure rate limiting
        Limiter(
            app,
            key_func=get_remote_address,
            default_limits=[f"{RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR']}/hour"],
            storage_uri=config_class.RATE_LIMIT_CONFIG['STORAGE_URL']
        )
        
        # Initialize health check endpoint
        init_health_check(app)
        
        # Initialize application routes and components
        init_app(app)
        
        # Register error handlers
        @app.errorhandler(Exception)
        def handle_exception(e):
            """Global exception handler with logging."""
            logger.error(
                f"Unhandled exception: {str(e)}",
                exc_info=True,
                extra={
                    'request_id': request.id,
                    'path': request.path,
                    'method': request.method
                }
            )
            return jsonify({
                'error': {
                    'code': 'SERVER_ERROR',
                    'message': ERROR_MESSAGES.get('SERVER_ERROR', 'An unexpected error occurred'),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            }), HTTP_STATUS_CODES['SERVER_ERROR']
        
        logger.info(f"Application initialized in {ENV} environment")
        return app
        
    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise

def configure_logging(env_name: str, app: Flask) -> None:
    """
    Configure environment-specific logging with request correlation.

    Args:
        env_name: Environment name
        app: Flask application instance
    """
    log_level = logging.DEBUG if env_name == 'development' else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(request_id)s] %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add request ID to log records
    class RequestIdFilter(logging.Filter):
        def filter(self, record):
            record.request_id = getattr(request, 'id', 'no-request-id')
            return True
            
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdFilter())
        
    logger.info(f"Logging configured for {env_name} environment")

def init_health_check(app: Flask) -> None:
    """
    Initialize health check endpoint with comprehensive system checks.

    Args:
        app: Flask application instance
    """
    @app.route('/health')
    def health_check():
        """Health check endpoint with system status."""
        try:
            # Perform system checks
            checks = {
                'database': check_database_health(),
                'cache': check_cache_health(),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version': VERSION,
                'environment': ENV
            }
            
            status_code = (
                HTTP_STATUS_CODES['OK']
                if all(c.get('status') == 'healthy' for c in checks.values() if isinstance(c, dict))
                else HTTP_STATUS_CODES['SERVICE_UNAVAILABLE']
            )
            
            return jsonify({
                'status': 'healthy' if status_code == HTTP_STATUS_CODES['OK'] else 'degraded',
                'checks': checks
            }), status_code
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), HTTP_STATUS_CODES['SERVICE_UNAVAILABLE']

def check_database_health() -> dict:
    """Check database connectivity and connection pool metrics."""
    from .core.database import get_engine
    try:
        engine = get_engine()
        engine.execute('SELECT 1')
        return {
            'status': 'healthy',
            'pool_size': engine.pool.size(),
            'checkedin': engine.pool.checkedin(),
            'overflow': engine.pool.overflow()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }

def check_cache_health() -> dict:
    """Check Redis cache connectivity and metrics."""
    from .core.cache import get_redis_client
    try:
        client = get_redis_client()
        client.ping()
        info = client.info(section='memory')
        return {
            'status': 'healthy',
            'used_memory': info.get('used_memory_human'),
            'peak_memory': info.get('used_memory_peak_human'),
            'fragmentation_ratio': info.get('mem_fragmentation_ratio')
        }
    except Exception as e:
        logger.error(f"Cache health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }