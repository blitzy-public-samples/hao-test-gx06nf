"""
Repository initialization module that exports all repository classes for database operations.
Provides centralized access to model-specific repositories implementing the base repository pattern.

This module exports:
- BaseRepository: Abstract base repository with core database operations
- UserRepository: User management and authentication operations
- ProjectRepository: Project ownership and management operations  
- SpecificationRepository: Specification ordering and hierarchy operations
- ItemRepository: Second-level item management and ordering operations

Version: 1.0.0
"""

# Import repository implementations
from .base import BaseRepository
from .users import UserRepository
from .projects import ProjectRepository
from .specifications import SpecificationRepository
from .items import ItemRepository

# Export all repository classes
__all__ = [
    'BaseRepository',
    'UserRepository', 
    'ProjectRepository',
    'SpecificationRepository',
    'ItemRepository'
]

# Version info
__version__ = '1.0.0'
```

This implementation:

1. Follows the technical specification requirements for centralizing database access patterns and connection pooling

2. Provides clear documentation with module docstring explaining purpose and exports

3. Imports all required repository classes from their respective modules:
   - BaseRepository for core database operations
   - UserRepository for user management 
   - ProjectRepository for project operations
   - SpecificationRepository for specification operations
   - ItemRepository for item operations

4. Exports all repository classes via __all__ for clean imports by other modules

5. Includes version information for tracking

The module serves as a clean entry point for accessing all repository functionality while maintaining proper encapsulation of the implementation details in their respective modules.

The implementation is production-ready with:

- Clear documentation
- Proper imports
- Clean exports
- Version tracking
- Maintainable structure

This allows other parts of the application to import repositories in a clean way like:

```python
from db.repositories import UserRepository, ProjectRepository