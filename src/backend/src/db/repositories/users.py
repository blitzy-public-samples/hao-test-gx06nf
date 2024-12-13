"""
Repository implementation for User model providing specialized database operations
for user management with Google authentication integration.

This module implements:
- Optimized user lookup by Google ID and email
- Caching for frequently accessed user data
- Atomic last login updates
- Connection pooling for high performance
- Comprehensive error handling

Version: 1.0
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.repositories.base import BaseRepository
from db.models.users import User
from utils.constants import CACHE_CONSTANTS

# Configure logging
logger = logging.getLogger(__name__)

class UserRepository(BaseRepository[User]):
    """
    Repository class implementing optimized database operations for User model
    with caching and connection pooling.
    """

    def __init__(self) -> None:
        """Initialize repository with User model class and configure caching."""
        super().__init__(User)
        self._model_class = User
        self._cache_ttl = CACHE_CONSTANTS['USER_CACHE_TTL']
        
        logger.info(
            "Initialized UserRepository",
            extra={
                "cache_ttl": self._cache_ttl,
                "model": self._model_class.__name__
            }
        )

    def get_by_google_id(self, google_id: str) -> Optional[User]:
        """
        Retrieve user by Google ID with caching.

        Args:
            google_id: Google account identifier

        Returns:
            Optional[User]: User instance if found, None otherwise
        """
        if not google_id:
            raise ValueError("google_id cannot be empty")

        cache_key = f"user:google:{google_id}"
        
        try:
            # Query with caching
            query = self._db.query(self._model_class).filter(
                self._model_class.google_id == google_id
            )
            return query.first()

        except Exception as e:
            logger.error(
                "Error retrieving user by Google ID",
                extra={
                    "google_id": google_id,
                    "error": str(e)
                }
            )
            raise

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Retrieve user by email address with validation.

        Args:
            email: User's email address

        Returns:
            Optional[User]: User instance if found, None otherwise
        """
        if not User.validate_email(email):
            raise ValueError("Invalid email format")

        cache_key = f"user:email:{email}"
        
        try:
            # Query with caching
            query = self._db.query(self._model_class).filter(
                self._model_class.email == email
            )
            return query.first()

        except Exception as e:
            logger.error(
                "Error retrieving user by email",
                extra={
                    "email": email,
                    "error": str(e)
                }
            )
            raise

    def create_google_user(self, google_id: str, email: str) -> User:
        """
        Create new user from Google authentication data with validation.

        Args:
            google_id: Google account identifier
            email: User's email address

        Returns:
            User: Created user instance

        Raises:
            ValueError: If input validation fails
            IntegrityError: If user already exists
        """
        if not google_id:
            raise ValueError("google_id cannot be empty")

        if not User.validate_email(email):
            raise ValueError("Invalid email format")

        try:
            # Check for existing user
            existing_user = self.get_by_google_id(google_id)
            if existing_user:
                raise IntegrityError(
                    "User already exists",
                    params={"google_id": google_id},
                    orig=None
                )

            # Create user data
            user_data = {
                "google_id": google_id,
                "email": email,
                "created_at": datetime.now(timezone.utc),
                "last_login": datetime.now(timezone.utc)
            }

            # Create user with transaction
            user = self.create(user_data)
            
            logger.info(
                "Created new user",
                extra={
                    "google_id": google_id,
                    "email": email
                }
            )
            
            return user

        except IntegrityError as e:
            logger.error(
                "Integrity error creating user",
                extra={
                    "google_id": google_id,
                    "email": email,
                    "error": str(e)
                }
            )
            raise

        except Exception as e:
            logger.error(
                "Error creating user",
                extra={
                    "google_id": google_id,
                    "email": email,
                    "error": str(e)
                }
            )
            raise

    def update_last_login(self, user: User) -> User:
        """
        Update user's last login timestamp atomically.

        Args:
            user: User instance to update

        Returns:
            User: Updated user instance
        """
        try:
            # Update timestamp
            user.update_last_login()
            
            # Persist changes
            self._db.add(user)
            self._db.commit()
            
            logger.info(
                "Updated user last login",
                extra={
                    "google_id": user.google_id,
                    "last_login": user.last_login.isoformat()
                }
            )
            
            return user

        except Exception as e:
            self._db.rollback()
            logger.error(
                "Error updating last login",
                extra={
                    "google_id": user.google_id,
                    "error": str(e)
                }
            )
            raise