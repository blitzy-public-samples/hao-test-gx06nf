"""
SQLAlchemy model definition for users table that stores Google-authenticated user information
and manages relationships with owned projects.

This module implements:
- User profile storage with Google authentication data
- Database schema for users table with required fields
- Secure user data storage with appropriate field types
- Project ownership relationships
- Data validation and serialization

Version: 1.0
"""

from datetime import datetime, timezone
import re
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.sql import expression

from db.session import Base

# Email validation regex pattern
EMAIL_REGEX: str = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

class User(Base):
    """
    SQLAlchemy model representing a Google-authenticated user with owned projects.
    
    Attributes:
        google_id (str): Primary key, unique Google account identifier
        email (str): User's email address, unique and indexed
        created_at (datetime): Timestamp of user creation
        last_login (datetime): Timestamp of user's last login
        projects (relationship): One-to-many relationship with owned projects
    """
    
    __tablename__ = 'users'

    # Primary Fields
    google_id = Column(
        String(50), 
        primary_key=True,
        index=True,
        nullable=False,
        comment='Unique Google account identifier'
    )
    
    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment='User email address'
    )
    
    # Timestamp Fields
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment='User creation timestamp'
    )
    
    last_login = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment='Last login timestamp'
    )

    # Relationships
    projects = relationship(
        'Project',
        back_populates='owner',
        cascade='all, delete-orphan',
        lazy='select',
        comment='Projects owned by this user'
    )

    def __init__(self, google_id: str, email: str) -> None:
        """
        Initialize a new User instance with validation.

        Args:
            google_id (str): Google account identifier
            email (str): User's email address

        Raises:
            ValueError: If google_id is empty or email format is invalid
        """
        if not google_id:
            raise ValueError("google_id cannot be empty")
        
        if not self.validate_email(email):
            raise ValueError("Invalid email format")

        self.google_id = google_id
        self.email = email
        self.created_at = datetime.now(timezone.utc)
        self.last_login = datetime.now(timezone.utc)

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validates email format using regex pattern.

        Args:
            email (str): Email address to validate

        Returns:
            bool: True if email is valid, False otherwise
        """
        if not email:
            return False
        return bool(re.match(EMAIL_REGEX, email))

    def update_last_login(self) -> None:
        """
        Updates the last_login timestamp to current UTC time.
        """
        self.last_login = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts user instance to dictionary for serialization.

        Returns:
            Dict[str, Any]: Dictionary containing user data without sensitive information
        """
        return {
            'google_id': self.google_id,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat()
        }

    def __repr__(self) -> str:
        """
        String representation of User instance.

        Returns:
            str: User representation with email
        """
        return f"<User {self.email}>"