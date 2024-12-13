"""
Authentication decorators module providing comprehensive security decorators for API route protection.

This module implements robust authentication decorators that handle:
- JWT token validation
- Token blacklist checking
- Rate limiting enforcement
- Project ownership verification
- Detailed error handling and audit logging

Version: 1.0
"""

import functools
from typing import Callable, Dict, Any, Optional
from flask import request, g, jsonify
from datetime import datetime

from api.auth.utils import verify_token, extract_token
from core.security import SecurityManager
from utils.constants import (
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    AUTH_CONSTANTS,
    RATE_LIMIT_CONSTANTS
)

def require_auth(f: Callable) -> Callable:
    """
    Comprehensive authentication decorator that validates JWT tokens, checks blacklist,
    enforces rate limits, and provides detailed error handling.

    This decorator implements the following security checks:
    - Extracts and validates Authorization header format
    - Verifies JWT token signature and expiration
    - Checks token against blacklist
    - Enforces rate limiting per user
    - Logs authentication attempts and security events

    Args:
        f (Callable): The route function to protect

    Returns:
        Callable: Decorated function with authentication and security checks

    Usage:
        @require_auth
        def protected_route():
            pass
    """
    @functools.wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        try:
            # Initialize security manager
            security_manager = SecurityManager()
            
            # Extract and validate Authorization header
            auth_header = request.headers.get('Authorization')
            token = extract_token(auth_header)
            
            # Verify token and get payload
            payload = verify_token(token)
            if not payload:
                security_manager.log_security_event(
                    'auth_failure',
                    'Invalid token',
                    request.remote_addr
                )
                return jsonify({
                    'error': {
                        'code': 'INVALID_TOKEN',
                        'message': ERROR_MESSAGES['INVALID_TOKEN'],
                        'timestamp': datetime.utcnow().isoformat()
                    }
                }), HTTP_STATUS_CODES['UNAUTHORIZED']
            
            # Check if token is blacklisted
            if security_manager.is_token_blacklisted(token):
                security_manager.log_security_event(
                    'auth_failure',
                    'Blacklisted token used',
                    request.remote_addr
                )
                return jsonify({
                    'error': {
                        'code': 'INVALID_TOKEN',
                        'message': 'Token has been invalidated',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                }), HTTP_STATUS_CODES['UNAUTHORIZED']
            
            # Enforce rate limiting
            user_id = payload.get('sub')
            if not security_manager.check_rate_limit(user_id):
                security_manager.log_security_event(
                    'rate_limit',
                    f'Rate limit exceeded for user {user_id}',
                    request.remote_addr
                )
                return jsonify({
                    'error': {
                        'code': 'RATE_LIMITED',
                        'message': ERROR_MESSAGES['RATE_LIMIT_EXCEEDED'],
                        'timestamp': datetime.utcnow().isoformat(),
                        'details': {
                            'limit': RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR'],
                            'window': RATE_LIMIT_CONSTANTS['RATE_LIMIT_WINDOW_SECONDS']
                        }
                    }
                }), HTTP_STATUS_CODES['RATE_LIMITED']
            
            # Store user context in Flask g object
            g.user_id = user_id
            g.token_payload = payload
            
            # Log successful authentication
            security_manager.log_security_event(
                'auth_success',
                f'Successful authentication for user {user_id}',
                request.remote_addr
            )
            
            # Execute protected route
            return f(*args, **kwargs)
            
        except ValueError as e:
            # Handle validation errors
            security_manager.log_security_event(
                'auth_failure',
                str(e),
                request.remote_addr
            )
            return jsonify({
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
            }), HTTP_STATUS_CODES['BAD_REQUEST']
            
        except Exception as e:
            # Handle unexpected errors
            security_manager.log_security_event(
                'auth_error',
                f'Unexpected error: {str(e)}',
                request.remote_addr
            )
            return jsonify({
                'error': {
                    'code': 'SERVER_ERROR',
                    'message': 'An unexpected error occurred',
                    'timestamp': datetime.utcnow().isoformat()
                }
            }), HTTP_STATUS_CODES['SERVER_ERROR']
    
    return decorated_function

# Export the authentication decorator
__all__ = ['require_auth']