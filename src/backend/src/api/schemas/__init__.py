"""
Package initialization file for API schema definitions.
Exports all Pydantic models for request/response validation and serialization
in the two-level specification hierarchy.

This module centralizes schema exports for:
- User authentication and profile data
- Project management and ownership
- Specification hierarchy (two levels)
- Item management within specifications

Version: 1.0.0
"""

# User-related schemas
from .users import (  # v1.0.0
    UserBase,
    UserCreate,
    UserResponse
)

# Project-related schemas
from .projects import (  # v1.0.0
    ProjectBase,
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse
)

# Specification-related schemas
from .specifications import (  # v1.0.0
    SpecificationBase,
    SpecificationCreate,
    SpecificationUpdate,
    SpecificationInDB
)

# Item-related schemas
from .items import (  # v1.0.0
    ItemBase,
    ItemCreate,
    ItemUpdate,
    ItemInDB
)

# Export all schemas for API usage
__all__ = [
    # User schemas
    'UserBase',
    'UserCreate', 
    'UserResponse',
    
    # Project schemas
    'ProjectBase',
    'ProjectCreate',
    'ProjectUpdate',
    'ProjectResponse',
    
    # Specification schemas
    'SpecificationBase',
    'SpecificationCreate',
    'SpecificationUpdate',
    'SpecificationInDB',
    
    # Item schemas
    'ItemBase',
    'ItemCreate',
    'ItemUpdate',
    'ItemInDB'
]