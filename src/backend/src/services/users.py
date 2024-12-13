"""
User service implementation providing high-level business logic for user management
with Google authentication integration, enhanced caching, security features, and
performance optimizations.

This module implements:
- User authentication with Google OAuth
- User profile management with caching
- Rate limiting and security controls
- Performance optimizations and monitoring

Version: 1.0
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from db.repositories.users import UserRepository
from api.auth.google import GoogleAuthClient, AuthenticationError, ProfileError
from core.cache import get_cache, set_cache, delete_cache
from utils.constants import CACHE_CONSTANTS, ERROR_MESSAGES, HTTP_STATUS_CODES

# Configure logging
logger = logging.getLogger(__name__)

# Constants
USER_CACHE_TTL = CACHE_CONSTANTS['USER_CACHE_TTL']  # 15 minutes
USER_CACHE_PREFIX = 'user:'
MAX_AUTH_ATTEMPTS = 5
AUTH_LOCKOUT_DURATION = 900  # 15 minutes

class UserService:
    """
    Enhanced service class implementing business logic for user management with
    security, caching, and performance optimizations.
    """

    def __init__(self) -> None:
        """Initialize service with repository, auth client, and security tracking."""
        self._repository = UserRepository()
        self._auth_client = GoogleAuthClient()
        self._auth_attempts: Dict[str, list] = {}

        logger.info(
            "Initialized UserService",
            extra={
                "cache_ttl": USER_CACHE_TTL,
                "max_auth_attempts": MAX_AUTH_ATTEMPTS
            }
        )

    def authenticate_google_user(self, token: str, client_ip: str) -> Dict[str, Any]:
        """
        Authenticate user with Google OAuth token with enhanced security and caching.

        Args:
            token: Google OAuth token
            client_ip: Client IP address for rate limiting

        Returns:
            Dict[str, Any]: User data with authentication status

        Raises:
            AuthenticationError: If authentication fails
            ValueError: If token is invalid
        """
        try:
            # Verify OAuth token with security checks
            token_info = self._auth_client.verify_oauth_token(token)
            google_id = token_info['sub']

            # Check cache for existing user
            cache_key = f"{USER_CACHE_PREFIX}google:{google_id}"
            cached_user = get_cache(cache_key)

            if cached_user:
                logger.info(
                    "User found in cache",
                    extra={"google_id": google_id}
                )
                return cached_user

            # Get user profile from Google
            profile = self._auth_client.get_user_profile(token)

            # Get or create user in database
            user = self._repository.get_by_google_id(google_id)
            if not user:
                user = self._repository.create_google_user(
                    google_id=google_id,
                    email=profile['email']
                )
                logger.info(
                    "Created new user",
                    extra={"google_id": google_id, "email": profile['email']}
                )
            else:
                # Update last login
                user = self._repository.update_last_login(user)
                logger.info(
                    "Updated user last login",
                    extra={"google_id": google_id}
                )

            # Prepare response data
            user_data = {
                **user.to_dict(),
                "authenticated": True,
                "token_exp": token_info.get('exp'),
                "auth_time": datetime.now(timezone.utc).isoformat()
            }

            # Cache user data
            set_cache(cache_key, user_data, USER_CACHE_TTL)

            return user_data

        except AuthenticationError as e:
            logger.error(
                "Authentication failed",
                extra={
                    "error": str(e),
                    "client_ip": client_ip
                }
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error during authentication",
                extra={
                    "error": str(e),
                    "client_ip": client_ip
                }
            )
            raise

    def get_user_by_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user by Google ID with enhanced caching and performance.

        Args:
            google_id: Google account identifier

        Returns:
            Optional[Dict[str, Any]]: User data if found

        Raises:
            ValueError: If google_id is invalid
        """
        if not google_id:
            raise ValueError("google_id cannot be empty")

        try:
            # Check cache first
            cache_key = f"{USER_CACHE_PREFIX}google:{google_id}"
            cached_user = get_cache(cache_key)

            if cached_user:
                logger.info(
                    "User retrieved from cache",
                    extra={"google_id": google_id}
                )
                return cached_user

            # Get from database if not in cache
            user = self._repository.get_by_google_id(google_id)
            if not user:
                return None

            # Prepare user data
            user_data = user.to_dict()

            # Cache user data
            set_cache(cache_key, user_data, USER_CACHE_TTL)

            logger.info(
                "User retrieved from database",
                extra={"google_id": google_id}
            )
            return user_data

        except Exception as e:
            logger.error(
                "Error retrieving user",
                extra={
                    "google_id": google_id,
                    "error": str(e)
                }
            )
            raise

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user by email with enhanced caching and security.

        Args:
            email: User's email address

        Returns:
            Optional[Dict[str, Any]]: User data if found

        Raises:
            ValueError: If email format is invalid
        """
        if not email:
            raise ValueError("email cannot be empty")

        try:
            # Check cache first
            cache_key = f"{USER_CACHE_PREFIX}email:{email}"
            cached_user = get_cache(cache_key)

            if cached_user:
                logger.info(
                    "User retrieved from cache",
                    extra={"email": email}
                )
                return cached_user

            # Get from database if not in cache
            user = self._repository.get_by_email(email)
            if not user:
                return None

            # Prepare user data
            user_data = user.to_dict()

            # Cache user data
            set_cache(cache_key, user_data, USER_CACHE_TTL)

            logger.info(
                "User retrieved from database",
                extra={"email": email}
            )
            return user_data

        except Exception as e:
            logger.error(
                "Error retrieving user by email",
                extra={
                    "email": email,
                    "error": str(e)
                }
            )
            raise

    def invalidate_user_cache(self, google_id: str) -> bool:
        """
        Invalidate user cache entries with enhanced pattern support.

        Args:
            google_id: Google account identifier

        Returns:
            bool: True if cache was invalidated successfully
        """
        try:
            # Get user to invalidate email cache as well
            user = self._repository.get_by_google_id(google_id)
            if not user:
                return False

            # Delete cache entries
            google_key = f"{USER_CACHE_PREFIX}google:{google_id}"
            email_key = f"{USER_CACHE_PREFIX}email:{user.email}"

            delete_cache(google_key)
            delete_cache(email_key)

            logger.info(
                "User cache invalidated",
                extra={"google_id": google_id}
            )
            return True

        except Exception as e:
            logger.error(
                "Error invalidating user cache",
                extra={
                    "google_id": google_id,
                    "error": str(e)
                }
            )
            raise