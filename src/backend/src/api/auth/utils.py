"""
Authentication utility module providing comprehensive token handling, validation,
and blacklist management with Redis-backed token invalidation.

This module implements core authentication utilities including token validation,
extraction, and blacklist management using Redis for token invalidation storage.

Version: 1.0
"""

import jwt  # version: 2.0+
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import redis  # version: 4.0+

from config.security import SecurityConfig
from utils.constants import AUTH_CONSTANTS, ERROR_MESSAGES, HTTP_STATUS_CODES

# Constants for token handling
BEARER_PREFIX: str = AUTH_CONSTANTS['BEARER_TOKEN_PREFIX']
TOKEN_BLACKLIST_PREFIX: str = 'token_blacklist:'
TOKEN_EXPIRY_BUFFER: int = 300  # 5 minutes buffer for token expiry

class AuthError(Exception):
    """Custom exception for authentication-related errors."""
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class AuthUtils:
    """
    Authentication utility class providing token handling and validation
    with Redis blacklist integration.
    """
    
    def __init__(self):
        """Initialize authentication utilities with Redis connection."""
        self._secret_key: str = SecurityConfig.JWT_SECRET_KEY
        self._algorithm: str = SecurityConfig.JWT_ALGORITHM
        self._token_expiry_buffer: int = TOKEN_EXPIRY_BUFFER
        
        # Initialize Redis client for blacklist management
        try:
            self._redis_client = redis.Redis(
                host=SecurityConfig.REDIS_HOST,
                port=SecurityConfig.REDIS_PORT,
                decode_responses=True
            )
            # Verify Redis connection
            self._redis_client.ping()
        except redis.ConnectionError as e:
            raise AuthError(
                "Failed to connect to Redis for token management",
                HTTP_STATUS_CODES['SERVICE_UNAVAILABLE']
            ) from e

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validates a token's signature, claims, and blacklist status.

        Args:
            token (str): The JWT token to validate

        Returns:
            Dict[str, Any]: Validated token payload

        Raises:
            AuthError: If token validation fails
        """
        try:
            # Remove Bearer prefix if present
            token = extract_token(token)
            
            # Verify token signature and decode payload
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm]
            )
            
            # Validate token expiration
            if datetime.utcfromtimestamp(payload['exp']) < datetime.utcnow():
                raise AuthError(
                    ERROR_MESSAGES['INVALID_TOKEN'],
                    HTTP_STATUS_CODES['UNAUTHORIZED']
                )
            
            # Check if token is blacklisted
            if self.is_token_blacklisted(token):
                raise AuthError(
                    "Token has been invalidated",
                    HTTP_STATUS_CODES['UNAUTHORIZED']
                )
            
            return payload
            
        except jwt.InvalidTokenError as e:
            raise AuthError(
                str(e),
                HTTP_STATUS_CODES['UNAUTHORIZED']
            ) from e
        except Exception as e:
            raise AuthError(
                "Token validation failed",
                HTTP_STATUS_CODES['UNAUTHORIZED']
            ) from e

    def blacklist_token(self, token: str) -> bool:
        """
        Adds a token to the Redis blacklist with appropriate TTL.

        Args:
            token (str): The JWT token to blacklist

        Returns:
            bool: True if blacklisting successful

        Raises:
            AuthError: If blacklisting operation fails
        """
        try:
            # Decode token without verification to get expiration
            payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )
            
            # Calculate remaining TTL
            exp_timestamp = payload['exp']
            current_timestamp = datetime.utcnow().timestamp()
            ttl = max(
                int(exp_timestamp - current_timestamp) + self._token_expiry_buffer,
                0
            )
            
            # Add to blacklist with TTL
            blacklist_key = f"{TOKEN_BLACKLIST_PREFIX}{token}"
            return bool(self._redis_client.setex(
                blacklist_key,
                ttl,
                "1"
            ))
            
        except Exception as e:
            raise AuthError(
                "Failed to blacklist token",
                HTTP_STATUS_CODES['SERVER_ERROR']
            ) from e

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verifies and decodes a JWT token with comprehensive validation including blacklist check.

    Args:
        token (str): The token to verify

    Returns:
        Dict[str, Any]: Decoded token payload if valid

    Raises:
        AuthError: If token is invalid or verification fails
    """
    auth_utils = AuthUtils()
    return auth_utils.validate_token(token)

def extract_token(auth_header: Optional[str]) -> str:
    """
    Extracts and validates token format from authorization header.

    Args:
        auth_header (Optional[str]): Authorization header value

    Returns:
        str: Cleaned and validated token string

    Raises:
        AuthError: If token format is invalid
    """
    if not auth_header:
        raise AuthError(
            "No authorization header provided",
            HTTP_STATUS_CODES['UNAUTHORIZED']
        )

    parts = auth_header.split()
    
    if parts[0] != BEARER_PREFIX:
        raise AuthError(
            "Invalid authorization header format",
            HTTP_STATUS_CODES['UNAUTHORIZED']
        )
        
    if len(parts) != 2:
        raise AuthError(
            "Invalid token format",
            HTTP_STATUS_CODES['UNAUTHORIZED']
        )
        
    token = parts[1]
    
    if len(token) < AUTH_CONSTANTS['MIN_TOKEN_LENGTH']:
        raise AuthError(
            "Token length below minimum requirement",
            HTTP_STATUS_CODES['UNAUTHORIZED']
        )
        
    return token

def is_token_blacklisted(token: str) -> bool:
    """
    Checks if a token is in the Redis-backed blacklist.

    Args:
        token (str): The token to check

    Returns:
        bool: True if token is blacklisted, False otherwise
    """
    try:
        redis_client = redis.Redis(
            host=SecurityConfig.REDIS_HOST,
            port=SecurityConfig.REDIS_PORT,
            decode_responses=True
        )
        blacklist_key = f"{TOKEN_BLACKLIST_PREFIX}{token}"
        return bool(redis_client.exists(blacklist_key))
    except redis.ConnectionError:
        # If Redis is unavailable, assume token is not blacklisted
        # This prevents system lockout but should trigger monitoring alert
        return False

__all__ = [
    'verify_token',
    'extract_token',
    'is_token_blacklisted',
    'AuthUtils',
    'AuthError'
]