"""
SQLAlchemy models initialization module that exports all database models and establishes
the schema hierarchy for the Specification Management API.

This module provides a central point for model imports and exports, ensuring proper
model relationships and dependencies are maintained for:
- User authentication and profile management
- Project ownership and metadata
- Specification hierarchy and ordering
- Item management with count limitations

Version: 1.0.0
"""

# Import models with explicit version control
from .users import User  # v1.0.0 - User profile and authentication
from .projects import Project  # v1.0.0 - Project management
from .specifications import Specification  # v1.0.0 - Specification hierarchy
from .items import Item  # v1.0.0 - Second-level items

# Export all models for application use
__all__ = [
    'User',  # Google-authenticated user profiles
    'Project',  # User-owned projects
    'Specification',  # Top-level specifications
    'Item'  # Second-level items
]

# Verify model relationships are properly established
User.projects  # One-to-many: User -> Projects
Project.specifications  # One-to-many: Project -> Specifications
Specification.items  # One-to-many: Specification -> Items (max 10)