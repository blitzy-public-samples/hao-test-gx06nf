"""
User management endpoints implementing secure Google OAuth authentication, profile management,
and session handling with comprehensive security controls and monitoring.

This module implements:
- Google OAuth authentication flow
- User profile retrieval with caching
- Rate limiting and security controls
- Detailed error handling and audit logging

Version: 1.0
"""

import logging
from datetime import datetime
from typing import Dict, Any, Tuple

from flask import Blueprint, request, jsonify, g
from flask_caching import cache
from flask_timeout import timeout_after
from flask_limiter import RateLimiter

from services.users import UserService
from api.schemas.users import UserResponse
from api.auth.decorators import require_auth
from api.auth.utils import AuthError, extract_token, verify_token
from utils.constants import (
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    RATE_LIMIT_CONSTANTS,
    CACHE_CONSTANTS
)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Blueprint
users_bp = Blueprint('users', __name__, url_prefix='/api/v1/users')

# Initialize services
user_service = UserService()

# Initialize rate limiter
rate_limiter = RateLimiter(
    max_requests=RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR'],
    window_seconds=RATE_LIMIT_CONSTANTS['RATE_LIMIT_WINDOW_SECONDS']
)

@users_bp.route('/authenticate', methods=['POST'])
@rate_limiter.check_rate_limit
@timeout_after(30)
def authenticate() -> Tuple[Dict[str, Any], int]:
    """
    Authenticate user with Google OAuth token and create/update user profile.
    
    Returns:
        Tuple[Dict[str, Any], int]: Authentication response and HTTP status code
        
    Raises:
        AuthError: If authentication fails
    """
    try:
        # Validate request content type
        if not request.is_json:
            raise AuthError(
                "Content-Type must be application/json",
                HTTP_STATUS_CODES['BAD_REQUEST']
            )

        # Extract and validate token from request
        token_data = request.get_json()
        if not token_data or 'token' not in token_data:
            raise AuthError(
                "Missing OAuth token",
                HTTP_STATUS_CODES['BAD_REQUEST']
            )

        # Authenticate user with Google token
        user_data = user_service.authenticate_google_user(
            token_data['token'],
            request.remote_addr
        )

        # Cache user data
        cache_key = f"user:{user_data['google_id']}"
        cache.set(
            cache_key,
            user_data,
            timeout=CACHE_CONSTANTS['USER_CACHE_TTL']
        )

        logger.info(
            "User authenticated successfully",
            extra={
                "google_id": user_data['google_id'],
                "ip": request.remote_addr
            }
        )

        return {
            "status": "success",
            "data": user_data,
            "timestamp": datetime.utcnow().isoformat()
        }, HTTP_STATUS_CODES['OK']

    except AuthError as e:
        logger.error(
            "Authentication failed",
            extra={
                "error": str(e),
                "ip": request.remote_addr
            }
        )
        return {
            "error": {
                "code": "AUTH_ERROR",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        }, e.status_code

    except Exception as e:
        logger.error(
            "Unexpected error during authentication",
            extra={
                "error": str(e),
                "ip": request.remote_addr
            }
        )
        return {
            "error": {
                "code": "SERVER_ERROR",
                "message": ERROR_MESSAGES['SERVER_ERROR'],
                "timestamp": datetime.utcnow().isoformat()
            }
        }, HTTP_STATUS_CODES['SERVER_ERROR']

@users_bp.route('/profile', methods=['GET'])
@require_auth
@rate_limiter.check_rate_limit
@cache.cached(timeout=CACHE_CONSTANTS['USER_CACHE_TTL'])
@timeout_after(10)
def get_profile() -> Tuple[Dict[str, Any], int]:
    """
    Retrieve authenticated user's profile with caching.
    
    Returns:
        Tuple[Dict[str, Any], int]: User profile data and HTTP status code
        
    Raises:
        AuthError: If user is not found or unauthorized
    """
    try:
        # Get user ID from authenticated context
        user_id = g.user_id
        if not user_id:
            raise AuthError(
                ERROR_MESSAGES['UNAUTHORIZED_ACCESS'],
                HTTP_STATUS_CODES['UNAUTHORIZED']
            )

        # Get user data from service
        user_data = user_service.get_user_by_id(user_id)
        if not user_data:
            raise AuthError(
                ERROR_MESSAGES['RESOURCE_NOT_FOUND'],
                HTTP_STATUS_CODES['NOT_FOUND']
            )

        # Validate response schema
        response_data = UserResponse.from_orm(user_data)

        logger.info(
            "Profile retrieved successfully",
            extra={"google_id": user_id}
        )

        return {
            "status": "success",
            "data": response_data.dict(),
            "timestamp": datetime.utcnow().isoformat()
        }, HTTP_STATUS_CODES['OK']

    except AuthError as e:
        logger.error(
            "Profile retrieval failed",
            extra={
                "error": str(e),
                "user_id": getattr(g, 'user_id', None)
            }
        )
        return {
            "error": {
                "code": "AUTH_ERROR",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        }, e.status_code

    except Exception as e:
        logger.error(
            "Unexpected error retrieving profile",
            extra={
                "error": str(e),
                "user_id": getattr(g, 'user_id', None)
            }
        )
        return {
            "error": {
                "code": "SERVER_ERROR",
                "message": ERROR_MESSAGES['SERVER_ERROR'],
                "timestamp": datetime.utcnow().isoformat()
            }
        }, HTTP_STATUS_CODES['SERVER_ERROR']

@users_bp.errorhandler(AuthError)
def handle_auth_error(error: AuthError) -> Tuple[Dict[str, Any], int]:
    """
    Global error handler for authentication errors.
    
    Args:
        error (AuthError): Authentication error instance
        
    Returns:
        Tuple[Dict[str, Any], int]: Error response and HTTP status code
    """
    logger.error(
        "Authentication error occurred",
        extra={
            "error": str(error),
            "status_code": error.status_code,
            "ip": request.remote_addr
        }
    )
    
    return {
        "error": {
            "code": "AUTH_ERROR",
            "message": str(error),
            "timestamp": datetime.utcnow().isoformat()
        }
    }, error.status_code

# Export Blueprint
__all__ = ['users_bp']