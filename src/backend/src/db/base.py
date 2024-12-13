"""
Central SQLAlchemy model registry that imports and exposes all database models.
Prevents circular dependencies and provides a single source of truth for model imports.

This module serves as the central point for importing database models, ensuring proper
initialization order and preventing circular import issues. It exposes all models
through a single interface for use by other modules.

Version: 1.0.0
"""

# Import Base class for SQLAlchemy models
from .session import Base

# Import all models to register them with SQLAlchemy
from .models.users import User
from .models.projects import Project
from .models.specifications import Specification
from .models.items import Item

# Re-export all models and Base
__all__ = [
    'Base',  # SQLAlchemy declarative base
    'User',  # User model for authentication and project ownership
    'Project',  # Project model for specification grouping
    'Specification',  # First-level specification model
    'Item',  # Second-level item model
]

"""
Model Hierarchy:

User
 └── Project
      └── Specification
           └── Item

Relationships:
- User (1) ---> (N) Project
- Project (1) ---> (N) Specification
- Specification (1) ---> (N) Item (max 10)

Key Constraints:
- User: Identified by google_id
- Project: Owned by single user
- Specification: Belongs to single project
- Item: Belongs to single specification, max 10 per specification
"""