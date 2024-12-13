"""
Pydantic schema definitions for item validation and serialization in API requests and responses.
Implements comprehensive validation rules for second-level items within specifications.

Version: 1.0.0
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator, constr, conint  # pydantic v1.9+

from ...utils.validators import (
    validate_content_length,
    validate_order_index,
    validate_items_count,
    MAX_ITEMS_PER_SPECIFICATION,
)

class ItemBase(BaseModel):
    """
    Base Pydantic model for item validation with enhanced security measures.
    Implements strict content and ordering validation with security patterns.
    """
    content: constr(
        min_length=1,
        max_length=1000,
        regex=r'^[\w\s.,!?-]*$',
        strip_whitespace=True
    ) = Field(
        ...,
        description="Item content with strict validation and sanitization",
        example="Sample item content"
    )
    
    order_index: conint(ge=0, lt=1000000) = Field(
        ...,
        description="Zero-based ordering index for items within a specification",
        example=0
    )

    @validator('content', pre=True)
    def validate_content(cls, value: str) -> str:
        """
        Validates item content with enhanced security checks and sanitization.
        
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
        Validates item order index with strict bounds checking.
        
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
                "content": "Sample item content with proper formatting",
                "order_index": 0
            }
        }

class ItemCreate(ItemBase):
    """
    Schema for creating new items with strict foreign key validation.
    Extends ItemBase with specification relationship validation.
    """
    spec_id: conint(gt=0) = Field(
        ...,
        description="Foreign key reference to parent specification",
        example=1
    )

    @validator('spec_id')
    def validate_spec_items_limit(cls, value: int) -> int:
        """
        Validates that specification has not exceeded maximum items limit.
        
        Args:
            value: Specification ID to validate
            
        Returns:
            int: Validated specification ID
            
        Raises:
            ValueError: If items limit validation fails
        """
        if not isinstance(value, int) or value <= 0:
            raise ValueError("Invalid specification ID")
        
        return value

    class Config:
        """Pydantic model configuration"""
        schema_extra = {
            "example": {
                "content": "New item content",
                "order_index": 0,
                "spec_id": 1
            }
        }

class ItemUpdate(BaseModel):
    """
    Schema for updating existing items with optional fields and validation.
    Allows partial updates while maintaining data integrity.
    """
    content: Optional[constr(
        min_length=1,
        max_length=1000,
        regex=r'^[\w\s.,!?-]*$',
        strip_whitespace=True
    )] = Field(
        None,
        description="Updated item content with validation",
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
                "content": "Updated item content",
                "order_index": 1
            }
        }

class ItemInDB(ItemBase):
    """
    Schema for item representation in database with complete validation.
    Extends ItemBase with database-specific fields.
    """
    item_id: conint(gt=0) = Field(
        ...,
        description="Unique identifier for the item",
        example=1
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp of item creation",
        example="2024-01-20T12:00:00Z"
    )

    class Config:
        """Pydantic model configuration"""
        orm_mode = True
        schema_extra = {
            "example": {
                "item_id": 1,
                "content": "Database item content",
                "order_index": 0,
                "created_at": "2024-01-20T12:00:00Z"
            }
        }

class ItemResponse(ItemBase):
    """
    Schema for item representation in API responses with field selection.
    Ensures consistent and secure response format.
    """
    item_id: int = Field(
        ...,
        description="Unique identifier for the item",
        example=1
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp of item creation",
        example="2024-01-20T12:00:00Z"
    )

    class Config:
        """Pydantic model configuration"""
        schema_extra = {
            "example": {
                "item_id": 1,
                "content": "Response item content",
                "order_index": 0,
                "created_at": "2024-01-20T12:00:00Z"
            }
        }