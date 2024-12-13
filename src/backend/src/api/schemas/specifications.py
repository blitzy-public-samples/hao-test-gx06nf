"""
Pydantic schema definitions for specification validation and serialization in API requests and responses.
Implements comprehensive validation rules for top-level specifications within projects.

Version: 1.0.0
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator, constr, conint  # pydantic v1.9+

from ...utils.validators import (
    validate_content_length,
    validate_order_index
)
from .items import ItemResponse

class SpecificationBase(BaseModel):
    """
    Base Pydantic model for specification validation with enhanced security measures.
    Implements strict content and ordering validation with security patterns.
    """
    content: constr(
        min_length=1,
        max_length=1000,
        regex=r'^[\w\s.,!?-]*$',
        strip_whitespace=True
    ) = Field(
        ...,
        description="Specification content with strict validation and sanitization",
        example="Sample specification content"
    )
    
    order_index: conint(ge=0, lt=1000000) = Field(
        ...,
        description="Zero-based ordering index for specifications within a project",
        example=0
    )

    @validator('content', pre=True)
    def validate_content(cls, value: str) -> str:
        """
        Validates specification content with enhanced security checks and sanitization.
        
        Args:
            value: Raw content string to validate
            
        Returns:
            str: Sanitized and validated content string
            
        Raises:
            ValueError: If content validation fails
        """
        if not value or not isinstance(value, str):
            raise ValueError("Content must be a non-empty string")
            
        if not validate_content_length(value):
            raise ValueError(
                "Content length must be between 1 and 1000 characters and contain only allowed characters"
            )
        
        return value.strip()

    @validator('order_index', pre=True)
    def validate_order(cls, value: int) -> int:
        """
        Validates specification order index with strict bounds checking.
        
        Args:
            value: Order index to validate
            
        Returns:
            int: Validated order index
            
        Raises:
            ValueError: If order index validation fails
        """
        if not validate_order_index(value):
            raise ValueError("Order index must be a non-negative integer less than 1,000,000")
        
        return value

    class Config:
        """Pydantic model configuration"""
        json_schema_extra = {
            "example": {
                "content": "Sample specification content with proper formatting",
                "order_index": 0
            }
        }

class SpecificationCreate(SpecificationBase):
    """
    Schema for creating new specifications with strict foreign key validation.
    Extends SpecificationBase with project relationship validation.
    """
    project_id: conint(gt=0) = Field(
        ...,
        description="Foreign key reference to parent project",
        example=1
    )

    class Config:
        """Pydantic model configuration"""
        schema_extra = {
            "example": {
                "content": "New specification content",
                "order_index": 0,
                "project_id": 1
            }
        }

class SpecificationUpdate(BaseModel):
    """
    Schema for updating existing specifications with optional fields and validation.
    Allows partial updates while maintaining data integrity.
    """
    content: Optional[constr(
        min_length=1,
        max_length=1000,
        regex=r'^[\w\s.,!?-]*$',
        strip_whitespace=True
    )] = Field(
        None,
        description="Updated specification content with validation",
        example="Updated content"
    )
    
    order_index: Optional[conint(ge=0, lt=1000000)] = Field(
        None,
        description="Updated order index",
        example=1
    )

    @validator('content')
    def validate_optional_content(cls, value: Optional[str]) -> Optional[str]:
        """Validates optional content updates"""
        if value is not None and not validate_content_length(value):
            raise ValueError(
                "Content length must be between 1 and 1000 characters and contain only allowed characters"
            )
        return value

    @validator('order_index')
    def validate_optional_order(cls, value: Optional[int]) -> Optional[int]:
        """Validates optional order index updates"""
        if value is not None and not validate_order_index(value):
            raise ValueError("Order index must be a non-negative integer less than 1,000,000")
        return value

    class Config:
        """Pydantic model configuration"""
        schema_extra = {
            "example": {
                "content": "Updated specification content",
                "order_index": 1
            }
        }

class SpecificationInDB(SpecificationBase):
    """
    Schema for specification representation in database with complete validation.
    Extends SpecificationBase with database-specific fields and relationships.
    """
    spec_id: conint(gt=0) = Field(
        ...,
        description="Unique identifier for the specification",
        example=1
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp of specification creation",
        example="2024-01-20T12:00:00Z"
    )
    items: List[ItemResponse] = Field(
        default_factory=list,
        description="List of items belonging to this specification",
        max_items=10
    )

    class Config:
        """Pydantic model configuration"""
        orm_mode = True
        schema_extra = {
            "example": {
                "spec_id": 1,
                "content": "Database specification content",
                "order_index": 0,
                "created_at": "2024-01-20T12:00:00Z",
                "items": []
            }
        }

class SpecificationResponse(SpecificationBase):
    """
    Schema for specification representation in API responses with field selection.
    Ensures consistent and secure response format with nested items.
    """
    spec_id: int = Field(
        ...,
        description="Unique identifier for the specification",
        example=1
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp of specification creation",
        example="2024-01-20T12:00:00Z"
    )
    items: List[ItemResponse] = Field(
        default_factory=list,
        description="List of items belonging to this specification",
        max_items=10
    )

    class Config:
        """Pydantic model configuration"""
        schema_extra = {
            "example": {
                "spec_id": 1,
                "content": "Response specification content",
                "order_index": 0,
                "created_at": "2024-01-20T12:00:00Z",
                "items": []
            }
        }