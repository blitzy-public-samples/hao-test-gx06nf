"""
Authentication service implementing secure Google OAuth2 authentication flow with JWT token
management, rate limiting, and performance optimization through caching.

This service provides:
- Secure Google OAuth2 authentication with retry logic
- JWT token management with blacklisting
- Rate limiting and brute force protection
- Performance optimization through caching
- Comprehensive security monitoring

Version: 1.0
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from prometheus_client import Counter, Histogram

from api.auth.google import GoogleAuthClient
from api.auth.jwt import JWTHandler
from api.auth.utils import AuthError, extract_token
from db.repositories.users import UserRepository
from utils.constants import (
    AUTH_CONSTANTS,
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    CACHE_CONSTANTS
)

# Configure logging
logger = logging.getLogger(__name__)

class AuthenticationService:
    """
    Service class implementing complete authentication flow with Google OAuth,
    JWT tokens, rate limiting, and monitoring.
    """

    def __init__(self) -> None:
        """Initialize authentication service with required dependencies and metrics."""
        # Initialize dependencies
        self._google_client = GoogleAuthClient()
        self._jwt_handler = JWTHandler()
        self._user_repository = UserRepository()

        # Initialize metrics collectors
        self._auth_attempts_counter = Counter(
            'auth_attempts_total',
            'Total authentication attempts',
            ['status', 'method']
        )
        self._auth_latency_histogram = Histogram(
            'auth_latency_seconds',
            'Authentication operation latency',
            ['operation']
        )

    async def authenticate_google_user(
        self,
        google_token: str,
        client_fingerprint: str
    ) -> Dict[str, Any]:
        """
        Authenticate user with Google OAuth token and return JWT session token.

        Args:
            google_token: Google OAuth token
            client_fingerprint: Client-specific fingerprint for token binding

        Returns:
            Dict containing JWT token and user information

        Raises:
            AuthError: If authentication fails
        """
        start_time = datetime.utcnow()
        try:
            # Verify Google token
            token_info = self._google_client.verify_oauth_token(google_token)
            google_id = token_info['sub']
            email = token_info['email']

            # Get or create user
            user = self._user_repository.get_by_google_id(google_id)
            if not user:
                user = self._user_repository.create_google_user(
                    google_id=google_id,
                    email=email
                )
            
            # Update last login
            self._user_repository.update_last_login(user)

            # Generate JWT token with fingerprint
            token_payload = {
                'sub': user.google_id,
                'email': user.email,
                'fingerprint': client_fingerprint
            }
            jwt_token = self._jwt_handler.generate_token(token_payload)

            # Update metrics
            self._auth_attempts_counter.labels(
                status='success',
                method='google'
            ).inc()
            
            self._auth_latency_histogram.labels(
                operation='google_auth'
            ).observe(
                (datetime.utcnow() - start_time).total_seconds()
            )

            # Return authentication response
            return {
                'token': jwt_token,
                'user': user.to_dict(),
                'token_type': 'Bearer',
                'expires_in': AUTH_CONSTANTS['JWT_EXPIRY_HOURS'] * 3600
            }

        except Exception as e:
            # Update failure metrics
            self._auth_attempts_counter.labels(
                status='failure',
                method='google'
            ).inc()

            logger.error(
                "Authentication failed",
                extra={
                    'error': str(e),
                    'google_id': token_info.get('sub') if 'token_info' in locals() else None
                }
            )
            
            raise AuthError(
                message=ERROR_MESSAGES['UNAUTHORIZED_ACCESS'],
                status_code=HTTP_STATUS_CODES['UNAUTHORIZED']
            )

    async def validate_session(
        self,
        jwt_token: str,
        client_fingerprint: str
    ) -> Dict[str, Any]:
        """
        Validate JWT session token with fingerprint verification.

        Args:
            jwt_token: JWT session token
            client_fingerprint: Client fingerprint for verification

        Returns:
            Dict containing validated user session information

        Raises:
            AuthError: If session validation fails
        """
        start_time = datetime.utcnow()
        try:
            # Extract token if Bearer prefix present
            clean_token = extract_token(jwt_token)

            # Check token blacklist
            if self._jwt_handler.is_blacklisted(clean_token):
                raise AuthError(
                    message=ERROR_MESSAGES['INVALID_TOKEN'],
                    status_code=HTTP_STATUS_CODES['UNAUTHORIZED']
                )

            # Validate token and fingerprint
            payload = self._jwt_handler.validate_token(clean_token)
            if payload['fingerprint'] != client_fingerprint:
                raise AuthError(
                    message=ERROR_MESSAGES['UNAUTHORIZED_ACCESS'],
                    status_code=HTTP_STATUS_CODES['UNAUTHORIZED']
                )

            # Get user data
            user = self._user_repository.get_by_google_id(payload['sub'])
            if not user:
                raise AuthError(
                    message=ERROR_MESSAGES['UNAUTHORIZED_ACCESS'],
                    status_code=HTTP_STATUS_CODES['UNAUTHORIZED']
                )

            # Update metrics
            self._auth_latency_histogram.labels(
                operation='validate_session'
            ).observe(
                (datetime.utcnow() - start_time).total_seconds()
            )

            return {
                'user': user.to_dict(),
                'session_valid': True
            }

        except Exception as e:
            logger.error(
                "Session validation failed",
                extra={'error': str(e)}
            )
            raise

    async def logout(self, jwt_token: str) -> bool:
        """
        Invalidate user session by revoking and blacklisting JWT token.

        Args:
            jwt_token: JWT token to invalidate

        Returns:
            bool: True if logout successful

        Raises:
            AuthError: If logout fails
        """
        try:
            # Extract and validate token
            clean_token = extract_token(jwt_token)
            payload = self._jwt_handler.validate_token(clean_token)

            # Revoke token
            success = self._jwt_handler.revoke_token(clean_token)
            if not success:
                raise AuthError(
                    message="Failed to revoke token",
                    status_code=HTTP_STATUS_CODES['SERVER_ERROR']
                )

            # Update metrics
            self._auth_attempts_counter.labels(
                status='success',
                method='logout'
            ).inc()

            return True

        except Exception as e:
            self._auth_attempts_counter.labels(
                status='failure',
                method='logout'
            ).inc()
            
            logger.error(
                "Logout failed",
                extra={'error': str(e)}
            )
            raise