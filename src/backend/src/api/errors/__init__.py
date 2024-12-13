"""
Centralized error handling package for the Specification Management API.

This package provides a comprehensive error handling system with:
- Standardized exception classes for common error scenarios
- Consistent error response format with error codes and messages
- Security-focused error handling to prevent information leakage
- Integration with logging and monitoring systems
- Request tracking with correlation IDs

Version: 1.0.0
"""

from typing import Final

# Import exception classes
from .exceptions import (
    APIException,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    NotFoundError,
    RateLimitError
)

# Import error handlers
from .handlers import (
    handle_api_exception,
    handle_http_exception,
    handle_generic_error
)

# Package version
VERSION: Final[str] = '1.0.0'

# Export all public components
__all__ = [
    # Base exception
    'APIException',
    
    # Specific exceptions
    'AuthenticationError',  # 401 Unauthorized
    'AuthorizationError',   # 403 Forbidden
    'ValidationError',      # 400 Bad Request
    'NotFoundError',       # 404 Not Found
    'RateLimitError',      # 429 Too Many Requests
    
    # Error handlers
    'handle_api_exception',    # Handler for API exceptions
    'handle_http_exception',   # Handler for HTTP exceptions
    'handle_generic_error',    # Handler for unhandled exceptions
    
    # Version info
    'VERSION'
]

# Error response format documentation
ERROR_RESPONSE_FORMAT = {
    "error": {
        "code": "HTTP_STATUS_CODE",
        "message": "Human readable error message",
        "details": {
            "error_code": "ERROR_CODE",
            "additional": "context"
        },
        "correlation_id": "unique-request-id",
        "timestamp": "ISO-8601 timestamp"
    }
}

# Register error handlers with Flask application
def register_error_handlers(app):
    """
    Register all error handlers with the Flask application.

    Args:
        app: Flask application instance

    This function sets up centralized error handling for:
    - Custom API exceptions
    - Standard HTTP exceptions
    - Unhandled exceptions
    """
    app.register_error_handler(APIException, handle_api_exception)
    app.register_error_handler(Exception, handle_generic_error)
    
    # Register handlers for specific HTTP status codes
    for status_code in [400, 401, 403, 404, 429, 500]:
        app.register_error_handler(status_code, handle_http_exception)

# Error code mapping for monitoring
ERROR_CODE_MAPPING = {
    'INVALID_INPUT': 400,
    'UNAUTHORIZED': 401,
    'FORBIDDEN': 403,
    'NOT_FOUND': 404,
    'RATE_LIMITED': 429,
    'SERVER_ERROR': 500
}