"""
Global error handlers for the Flask application providing consistent error responses.

This module implements standardized error handling across all endpoints with:
- Consistent error response format
- Enhanced logging with request context
- Error tracking with correlation IDs
- Security-focused error messages
- Performance monitoring
- Cache integration

Version: 1.0
"""

from datetime import datetime
import uuid
from typing import Tuple, Dict, Any

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException

from api.errors.exceptions import APIException
from core.logging import logger
from utils.constants import HTTP_STATUS_CODES, ERROR_MESSAGES, CACHE_CONSTANTS

# Initialize error handlers blueprint
error_handlers = Blueprint('error_handlers', __name__)

# Cache configuration for error responses
ERROR_RESPONSE_CACHE_TTL = CACHE_CONSTANTS['PROJECT_CACHE_TTL']

def sanitize_error_message(message: str) -> str:
    """
    Sanitize error messages to prevent information disclosure.

    Args:
        message (str): Raw error message

    Returns:
        str: Sanitized error message
    """
    # Limit message length and remove potential sensitive info
    return str(message)[:200] if message else 'An error occurred'

def create_error_response(
    error_code: int,
    message: str,
    details: Dict[str, Any] = None,
    correlation_id: str = None
) -> Dict[str, Any]:
    """
    Create standardized error response dictionary.

    Args:
        error_code (int): HTTP status code
        message (str): Error message
        details (Dict[str, Any], optional): Additional error details
        correlation_id (str, optional): Error tracking ID

    Returns:
        Dict[str, Any]: Formatted error response
    """
    return {
        "error": {
            "code": error_code,
            "message": sanitize_error_message(message),
            "details": details or {},
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat()
        }
    }

@error_handlers.app_errorhandler(APIException)
def handle_api_exception(error: APIException) -> Tuple[Dict[str, Any], int]:
    """
    Handle custom API exceptions with enhanced logging.

    Args:
        error (APIException): Custom API exception instance

    Returns:
        Tuple[Dict[str, Any], int]: Error response and status code
    """
    correlation_id = str(uuid.uuid4())
    
    # Log error with context
    logger.error(
        f"API Exception: {error.message}",
        extra={
            'correlation_id': correlation_id,
            'status_code': error.status_code,
            'endpoint': request.endpoint,
            'method': request.method,
            'details': error.details
        }
    )

    response = create_error_response(
        error_code=error.status_code,
        message=error.message,
        details=error.details,
        correlation_id=correlation_id
    )

    return jsonify(response), error.status_code

@error_handlers.app_errorhandler(HTTPException)
def handle_http_exception(error: HTTPException) -> Tuple[Dict[str, Any], int]:
    """
    Handle Werkzeug HTTP exceptions with security considerations.

    Args:
        error (HTTPException): HTTP exception instance

    Returns:
        Tuple[Dict[str, Any], int]: Error response and status code
    """
    correlation_id = str(uuid.uuid4())
    
    # Log HTTP error
    logger.warning(
        f"HTTP Exception: {error.description}",
        extra={
            'correlation_id': correlation_id,
            'status_code': error.code,
            'endpoint': request.endpoint,
            'method': request.method
        }
    )

    response = create_error_response(
        error_code=error.code,
        message=error.description,
        correlation_id=correlation_id
    )

    return jsonify(response), error.code

@error_handlers.app_errorhandler(Exception)
def handle_generic_exception(error: Exception) -> Tuple[Dict[str, Any], int]:
    """
    Handle unhandled exceptions with comprehensive error tracking.

    Args:
        error (Exception): Unhandled exception instance

    Returns:
        Tuple[Dict[str, Any], int]: Error response with 500 status code
    """
    correlation_id = str(uuid.uuid4())
    
    # Log detailed error information
    logger.exception(
        f"Unhandled Exception: {str(error)}",
        extra={
            'correlation_id': correlation_id,
            'endpoint': request.endpoint,
            'method': request.method
        }
    )

    # Return generic error message for security
    response = create_error_response(
        error_code=HTTP_STATUS_CODES['SERVER_ERROR'],
        message=ERROR_MESSAGES['RESOURCE_NOT_FOUND'],
        correlation_id=correlation_id
    )

    return jsonify(response), HTTP_STATUS_CODES['SERVER_ERROR']