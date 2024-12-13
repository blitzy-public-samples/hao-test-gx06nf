"""
Main entry point for the utils package providing centralized access to utility functions,
constants, validators, helpers and decorators used across the application.

This module exposes commonly used utilities for:
- Data validation and sanitization
- Performance monitoring and metrics
- Error handling and response formatting
- Caching implementation
- Security controls

Version: 1.0.0
"""

from typing import List, Dict, Any, Final

# Import database constants
from .constants import (
    DATABASE_CONSTANTS,
    AUTH_CONSTANTS,
    RATE_LIMIT_CONSTANTS,
    CACHE_CONSTANTS,
    API_CONSTANTS,
    HTTP_STATUS_CODES,
    ERROR_MESSAGES
)

# Import validators
from .validators import (
    validate_email,
    validate_content_length,
    validate_order_index,
    validate_items_count,
    validate_google_id
)

# Import helpers
from .helpers import (
    format_response,
    calculate_order_index,
    format_timestamp,
    safe_json_loads,
    generate_cache_key
)

# Import decorators
from .decorators import (
    require_auth,
    rate_limit,
    cache_response
)

# Package version
__version__: Final[str] = '1.0.0'

# Package metadata
__author__: Final[str] = 'Specification Management API Team'
__copyright__: Final[str] = '2024'

# Define public API
__all__: List[str] = [
    # Constants
    'DATABASE_CONSTANTS',
    'AUTH_CONSTANTS',
    'RATE_LIMIT_CONSTANTS',
    'CACHE_CONSTANTS',
    'API_CONSTANTS',
    'HTTP_STATUS_CODES',
    'ERROR_MESSAGES',
    
    # Validators
    'validate_email',
    'validate_content_length',
    'validate_order_index',
    'validate_items_count',
    'validate_google_id',
    
    # Helpers
    'format_response',
    'calculate_order_index',
    'format_timestamp',
    'safe_json_loads',
    'generate_cache_key',
    
    # Decorators
    'require_auth',
    'rate_limit',
    'cache_response',
    
    # Version
    '__version__'
]

def get_package_info() -> Dict[str, Any]:
    """
    Returns package metadata and version information.

    Returns:
        Dict[str, Any]: Dictionary containing package metadata
        
    Example:
        >>> get_package_info()
        {
            'version': '1.0.0',
            'author': 'Specification Management API Team',
            'copyright': '2024'
        }
    """
    return {
        'version': __version__,
        'author': __author__,
        'copyright': __copyright__
    }

# Initialize package-level logger
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Verify critical dependencies are available
try:
    import redis
    import jwt
    import flask
except ImportError as e:
    logger.critical(f"Critical dependency missing: {str(e)}")
    raise

# Log package initialization
logger.info(f"Utils package initialized - Version {__version__}")