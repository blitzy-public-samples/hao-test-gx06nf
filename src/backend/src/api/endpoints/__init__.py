"""
Initializes and exports all API endpoint blueprints for the Flask application.
Provides centralized access to health checks, user management, projects,
specifications and items endpoints with proper authentication, rate limiting
and security controls.

Version: 1.0.0
"""

import logging
from typing import List

from flask import Blueprint
from prometheus_client import Counter, Histogram

from .health import health_bp
from .users import users_bp
from .projects import projects_router
from .specifications import specifications_bp
from .items import items_bp

# Configure logging
logger = logging.getLogger(__name__)

# Initialize metrics
ENDPOINT_REQUESTS = Counter(
    'api_requests_total',
    'Total API endpoint requests',
    ['endpoint', 'method']
)

ENDPOINT_LATENCY = Histogram(
    'api_request_duration_seconds',
    'API endpoint request duration',
    ['endpoint', 'method']
)

# List of all API blueprints
API_BLUEPRINTS: List[Blueprint] = [
    health_bp,          # Health check endpoints
    users_bp,           # User authentication and profile management
    projects_router,    # Project CRUD operations
    specifications_bp,  # Specification management within projects
    items_bp           # Item management within specifications
]

def init_api_routes(app) -> None:
    """
    Register all API blueprints with the Flask application.
    Configures URL prefixes, error handlers, and monitoring.

    Args:
        app: Flask application instance
    """
    try:
        # Register blueprints with proper URL prefixes
        app.register_blueprint(health_bp, url_prefix='/health')
        app.register_blueprint(users_bp, url_prefix='/api/v1/users')
        app.register_blueprint(projects_router, url_prefix='/api/v1/projects')
        app.register_blueprint(specifications_bp, url_prefix='/api/v1/specifications')
        app.register_blueprint(items_bp, url_prefix='/api/v1/items')

        logger.info(
            "Successfully registered API blueprints",
            extra={"blueprint_count": len(API_BLUEPRINTS)}
        )

    except Exception as e:
        logger.error(
            "Failed to register API blueprints",
            extra={"error": str(e)},
            exc_info=True
        )
        raise

# Export blueprints and initialization function
__all__ = [
    'health_bp',
    'users_bp', 
    'projects_router',
    'specifications_bp',
    'items_bp',
    'init_api_routes',
    'API_BLUEPRINTS'
]