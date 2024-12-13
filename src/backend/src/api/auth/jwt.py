"""
JWT token management module implementing secure authentication token handling.

This module provides comprehensive JWT token management with:
- Secure token generation and validation
- Redis-backed token blacklist
- Thread-safe token validation caching
- Robust error handling and security controls

Version: 1.0
"""

import jwt  # version: 2.0+
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Final
import redis  # version: 4.0+
from threading import Lock

from config.security import SecurityConfig
from api.auth.utils import AuthUtils, extract_token, is_token_blacklisted
from core.cache import RedisClient

# Token-related constants
TOKEN_TYPE: Final[str] = 'access'
TOKEN_BLACKLIST_PREFIX: Final[str] = 'blacklist:'
TOKEN_CACHE_PREFIX: Final[str] = 'token_cache:'

class JWTHandler:
    """Thread-safe JWT token management class with caching and security features."""
    
    def __init__(self) -> None:
        """Initialize JWT handler with security configuration."""
        self._secret_key: str = SecurityConfig.JWT_SECRET_KEY
        self._algorithm: str = SecurityConfig.JWT_ALGORITHM
        self._redis_client: redis.Redis = RedisClient.get_connection()
        self._validation_cache: Dict[str, Any] = {}
        self._cache_lock = Lock()
        
        # Verify security configuration
        if not self._secret_key or len(self._secret_key) < 32:
            raise ValueError("Invalid JWT secret key configuration")
            
        if self._algorithm != 'HS256':
            raise ValueError("Unsupported JWT algorithm")

    def generate_token(self, payload: Dict[str, Any]) -> str:
        """
        Generates secure JWT token with validation.

        Args:
            payload (Dict[str, Any]): Token payload data

        Returns:
            str: Generated JWT token

        Raises:
            ValueError: If payload is invalid
            jwt.InvalidTokenError: If token generation fails
        """
        if not isinstance(payload, dict):
            raise ValueError("Token payload must be a dictionary")

        # Create token payload with security claims
        token_payload = payload.copy()
        token_payload.update({
            'iat': datetime.utcnow(),
            'exp': SecurityConfig.get_token_expiry(),
            'type': TOKEN_TYPE,
            # Add fingerprint for additional security
            'fingerprint': AuthUtils.generate_token_fingerprint(payload)
        })

        try:
            token = jwt.encode(
                token_payload,
                self._secret_key,
                algorithm=self._algorithm
            )
            
            # Verify generated token
            self.validate_token(token)
            
            # Cache initial validation
            with self._cache_lock:
                self._validation_cache[token] = {
                    'payload': token_payload,
                    'timestamp': datetime.utcnow()
                }
            
            return token
            
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Token generation failed: {str(e)}")

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validates JWT token with caching.

        Args:
            token (str): Token to validate

        Returns:
            Dict[str, Any]: Validated token payload

        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        # Check validation cache first
        with self._cache_lock:
            cached = self._validation_cache.get(token)
            if cached:
                cache_age = datetime.utcnow() - cached['timestamp']
                if cache_age.total_seconds() < 300:  # 5 minute cache
                    return cached['payload']

        try:
            # Extract token if it includes Bearer prefix
            clean_token = extract_token(token)
            
            # Check blacklist
            if is_token_blacklisted(clean_token):
                raise jwt.InvalidTokenError("Token has been revoked")

            # Decode and verify token
            payload = jwt.decode(
                clean_token,
                self._secret_key,
                algorithms=[self._algorithm]
            )

            # Validate token type
            if payload.get('type') != TOKEN_TYPE:
                raise jwt.InvalidTokenError("Invalid token type")

            # Validate fingerprint
            if not AuthUtils.verify_token_fingerprint(payload):
                raise jwt.InvalidTokenError("Invalid token fingerprint")

            # Update validation cache
            with self._cache_lock:
                self._validation_cache[clean_token] = {
                    'payload': payload,
                    'timestamp': datetime.utcnow()
                }

            return payload

        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Token validation failed: {str(e)}")

    def revoke_token(self, token: str) -> bool:
        """
        Revokes token with cache invalidation.

        Args:
            token (str): Token to revoke

        Returns:
            bool: True if token was successfully revoked

        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            # Validate token before revocation
            clean_token = extract_token(token)
            payload = self.validate_token(clean_token)

            # Calculate TTL for blacklist entry
            exp_time = datetime.fromtimestamp(payload['exp'])
            ttl = int((exp_time - datetime.utcnow()).total_seconds())

            # Add to blacklist with TTL
            blacklist_key = f"{TOKEN_BLACKLIST_PREFIX}{clean_token}"
            success = bool(self._redis_client.setex(
                blacklist_key,
                ttl,
                "1"
            ))

            # Clear validation cache
            with self._cache_lock:
                self._validation_cache.pop(clean_token, None)

            return success

        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Token revocation failed: {str(e)}")

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a new JWT access token with comprehensive security controls.

    Args:
        data (Dict[str, Any]): Token payload data
        expires_delta (Optional[timedelta]): Custom expiration time

    Returns:
        str: Encoded JWT token string

    Raises:
        ValueError: If data is invalid
    """
    handler = JWTHandler()
    
    # Set expiration time
    if expires_delta:
        expiry = datetime.utcnow() + expires_delta
    else:
        expiry = SecurityConfig.get_token_expiry()
    
    # Add expiration to payload
    payload = data.copy()
    payload['exp'] = expiry
    
    return handler.generate_token(payload)

def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates JWT token with blacklist check.

    Args:
        token (str): Token to decode and validate

    Returns:
        Dict[str, Any]: Decoded token payload

    Raises:
        jwt.InvalidTokenError: If token is invalid
    """
    handler = JWTHandler()
    return handler.validate_token(token)

def revoke_token(token: str) -> bool:
    """
    Revokes JWT token by adding to Redis-backed blacklist.

    Args:
        token (str): Token to revoke

    Returns:
        bool: True if token was successfully revoked

    Raises:
        jwt.InvalidTokenError: If token is invalid
    """
    handler = JWTHandler()
    return handler.revoke_token(token)