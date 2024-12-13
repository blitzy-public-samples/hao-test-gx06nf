"""
Pydantic schema definitions for user-related API request/response validation.

This module implements secure data transfer objects for:
- User profile data validation
- Google authentication responses
- Enhanced field validation with security measures

Version: 1.0
"""

from datetime import datetime
from typing import Optional
import re

from pydantic import BaseModel, Field, EmailStr, validator

# Import User model for ORM integration
from db.models.users import User

# Constants for validation
GOOGLE_ID_PATTERN = r'^[0-9]{21}$'  # Google ID format validation
MAX_EMAIL_LENGTH = 255
MIN_GOOGLE_ID_LENGTH = 21
MAX_GOOGLE_ID_LENGTH = 21

class UserBase(BaseModel):
    """
    Base Pydantic model for user data validation with enhanced security measures.
    
    Attributes:
        email (EmailStr): Validated user email address
    """
    email: EmailStr = Field(
        ...,  # Required field
        max_length=MAX_EMAIL_LENGTH,
        description="User's email address"
    )

    @validator('email')
    def validate_email(cls, value: str) -> str:
        """
        Custom email validator with additional security checks.
        
        Args:
            value (str): Email address to validate
            
        Returns:
            str: Validated email address
            
        Raises:
            ValueError: If email validation fails
        """
        if not value:
            raise ValueError("Email cannot be empty")
        
        if len(value) > MAX_EMAIL_LENGTH:
            raise ValueError(f"Email length cannot exceed {MAX_EMAIL_LENGTH} characters")
        
        # Check for common malicious patterns
        if re.search(r'[<>{}*$]', value):
            raise ValueError("Email contains invalid characters")
            
        return value.lower()  # Normalize email to lowercase

class UserCreate(UserBase):
    """
    Schema for secure user creation from Google authentication.
    
    Attributes:
        google_id (str): Validated Google account identifier
        email (EmailStr): Inherited from UserBase
    """
    google_id: str = Field(
        ...,  # Required field
        min_length=MIN_GOOGLE_ID_LENGTH,
        max_length=MAX_GOOGLE_ID_LENGTH,
        description="Google account identifier",
        regex=GOOGLE_ID_PATTERN
    )

    @validator('google_id')
    def validate_google_id(cls, value: str) -> str:
        """
        Custom validator for Google ID format and security.
        
        Args:
            value (str): Google ID to validate
            
        Returns:
            str: Validated Google ID
            
        Raises:
            ValueError: If Google ID validation fails
        """
        if not value:
            raise ValueError("Google ID cannot be empty")
        
        if not re.match(GOOGLE_ID_PATTERN, value):
            raise ValueError("Invalid Google ID format")
            
        return value

    class Config:
        """Pydantic model configuration."""
        schema_extra = {
            "example": {
                "google_id": "123456789012345678901",
                "email": "user@example.com"
            }
        }

class UserResponse(BaseModel):
    """
    Schema for secure user profile response data.
    
    Attributes:
        google_id (str): Google account identifier
        email (EmailStr): User's email address
        created_at (datetime): Account creation timestamp
        last_login (datetime): Last login timestamp
    """
    google_id: str = Field(
        ...,
        description="Google account identifier"
    )
    email: EmailStr = Field(
        ...,
        description="User's email address"
    )
    created_at: datetime = Field(
        ...,
        description="Account creation timestamp"
    )
    last_login: datetime = Field(
        ...,
        description="Last login timestamp"
    )

    @classmethod
    def from_orm(cls, db_obj: User) -> 'UserResponse':
        """
        Securely creates UserResponse from ORM model with validation.
        
        Args:
            db_obj (User): Database user model instance
            
        Returns:
            UserResponse: Validated response schema instance
            
        Raises:
            ValueError: If conversion validation fails
        """
        if not isinstance(db_obj, User):
            raise ValueError("Invalid input type for user conversion")
            
        return cls(
            google_id=db_obj.google_id,
            email=db_obj.email,
            created_at=db_obj.created_at,
            last_login=db_obj.last_login
        )

    class Config:
        """Pydantic model configuration."""
        orm_mode = True
        schema_extra = {
            "example": {
                "google_id": "123456789012345678901",
                "email": "user@example.com",
                "created_at": "2024-01-20T12:00:00Z",
                "last_login": "2024-01-20T12:00:00Z"
            }
        }