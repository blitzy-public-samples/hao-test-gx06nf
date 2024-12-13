"""
Service layer initialization module that exposes core application services.

This module provides centralized access to application services including:
- Authentication service for Google OAuth and session management
- Caching service for performance optimization
- Project management service for user projects
- Specification management service for project specifications

Version: 1.0.0
"""

from typing import Dict, Any, Optional
import logging

from .auth import AuthenticationService
from .cache import (
    cache_project_list,
    get_cached_project_list,
    cache_specifications,
    get_cached_specifications,
    cache_items,
    get_cached_items,
    invalidate_project_cache,
    invalidate_specification_cache
)
from .projects import ProjectService
from .specifications import SpecificationService

# Configure logging
logger = logging.getLogger(__name__)

# Initialize core services
try:
    # Initialize authentication service first as other services depend on it
    auth_service = AuthenticationService()
    logger.info("Initialized AuthenticationService")

    # Initialize caching service for performance optimization
    logger.info("Initialized CacheService functions")

    # Initialize project service with authentication dependency
    project_service = ProjectService()
    logger.info("Initialized ProjectService")

    # Initialize specification service with project dependency
    specification_service = SpecificationService()
    logger.info("Initialized SpecificationService")

except Exception as e:
    logger.critical(
        "Failed to initialize services",
        extra={"error": str(e)}
    )
    raise

# Export service instances and functions
__all__ = [
    # Service classes
    'AuthenticationService',
    'ProjectService',
    'SpecificationService',
    
    # Cache functions
    'cache_project_list',
    'get_cached_project_list',
    'cache_specifications', 
    'get_cached_specifications',
    'cache_items',
    'get_cached_items',
    'invalidate_project_cache',
    'invalidate_specification_cache'
]

# Service health check function
def check_services_health() -> Dict[str, Any]:
    """
    Check health status of all initialized services.

    Returns:
        Dict[str, Any]: Health status of each service
    """
    try:
        health_status = {
            "auth_service": auth_service is not None,
            "project_service": project_service is not None,
            "specification_service": specification_service is not None,
            "cache_service": True  # Cache functions are available
        }
        
        logger.info(
            "Services health check completed",
            extra={"status": health_status}
        )
        
        return health_status
        
    except Exception as e:
        logger.error(
            "Services health check failed",
            extra={"error": str(e)}
        )
        return {
            "error": "Services health check failed",
            "details": str(e)
        }