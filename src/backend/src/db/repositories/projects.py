"""
Repository implementation for Project model providing database operations for managing user-owned projects.
Implements the repository pattern with project-specific query methods, ownership validation,
caching integration, and comprehensive error handling.

Version: 1.0
"""

from typing import List, Optional, Dict
from sqlalchemy import and_, select, joinedload
from flask_caching import cache  # type: ignore # version: 1.10+

from .base import BaseRepository
from ..models.projects import Project
from ...utils.constants import (
    CACHE_CONSTANTS,
    DATABASE_CONSTANTS,
    ERROR_MESSAGES
)

class ProjectRepository(BaseRepository[Project]):
    """
    Repository class for managing Project model database operations with ownership validation,
    caching, and optimized query patterns.
    """

    _model_class = Project
    CACHE_TIMEOUT = CACHE_CONSTANTS['PROJECT_CACHE_TTL']

    def __init__(self) -> None:
        """Initialize project repository with Project model and cache configuration."""
        super().__init__(Project)

    @cache.memoize(timeout=CACHE_TIMEOUT)
    def get_by_owner(self, owner_id: str) -> List[Project]:
        """
        Get all projects owned by a specific user with caching and eager loading.

        Args:
            owner_id: Google ID of the project owner

        Returns:
            List[Project]: List of projects owned by the user

        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            query = (
                self._db.query(Project)
                .options(joinedload(Project.specifications))
                .filter(Project.owner_id == owner_id)
                .order_by(Project.updated_at.desc())
            )
            return query.all()
        except Exception as e:
            self._db.rollback()
            raise

    @cache.memoize(timeout=CACHE_TIMEOUT)
    def validate_owner(self, owner_id: str, project_id: int) -> bool:
        """
        Validate if a user owns a specific project with caching.

        Args:
            owner_id: Google ID of the potential owner
            project_id: ID of the project to validate

        Returns:
            bool: True if user owns project, False otherwise
        """
        try:
            exists_query = (
                select(1)
                .where(
                    and_(
                        Project.project_id == project_id,
                        Project.owner_id == owner_id
                    )
                )
                .exists()
            )
            return self._db.query(exists_query).scalar()
        except Exception as e:
            self._db.rollback()
            return False

    def create_project(self, owner_id: str, project_data: Dict[str, any]) -> Project:
        """
        Create a new project for a user with validation and timestamp.

        Args:
            owner_id: Google ID of the project owner
            project_data: Dictionary containing project data

        Returns:
            Project: Created project instance

        Raises:
            ValueError: If project data is invalid
            SQLAlchemyError: If database operation fails
        """
        try:
            # Validate project count for owner
            owner_projects = self.get_by_owner(owner_id)
            if len(owner_projects) >= DATABASE_CONSTANTS['MAX_SPECIFICATIONS_PER_PROJECT']:
                raise ValueError(ERROR_MESSAGES['MAX_ITEMS_REACHED'])

            # Prepare project data
            project_data['owner_id'] = owner_id
            
            # Create project
            project = super().create(project_data)
            
            # Invalidate owner's project cache
            cache.delete_memoized(self.get_by_owner, owner_id)
            
            return project
        except Exception as e:
            self._db.rollback()
            raise

    def update_project(
        self,
        owner_id: str,
        project_id: int,
        project_data: Dict[str, any]
    ) -> Optional[Project]:
        """
        Update a project if user is owner with timestamp update.

        Args:
            owner_id: Google ID of the project owner
            project_id: ID of the project to update
            project_data: Dictionary containing updated project data

        Returns:
            Optional[Project]: Updated project if successful, None if not owner

        Raises:
            ValueError: If project data is invalid
            SQLAlchemyError: If database operation fails
        """
        try:
            # Validate ownership
            if not self.validate_owner(owner_id, project_id):
                return None

            # Get project with locking
            project = (
                self._db.query(Project)
                .filter(Project.project_id == project_id)
                .with_for_update()
                .first()
            )

            if not project:
                return None

            # Update timestamp
            project.update_timestamp()
            
            # Update project
            updated_project = super().update(project_id, project_data)
            
            # Invalidate caches
            cache.delete_memoized(self.get_by_owner, owner_id)
            cache.delete_memoized(self.validate_owner, owner_id, project_id)
            
            return updated_project
        except Exception as e:
            self._db.rollback()
            raise

    def delete_project(self, owner_id: str, project_id: int) -> bool:
        """
        Delete a project if user is owner with cache cleanup.

        Args:
            owner_id: Google ID of the project owner
            project_id: ID of the project to delete

        Returns:
            bool: True if deleted, False if not owner

        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            # Validate ownership
            if not self.validate_owner(owner_id, project_id):
                return False

            # Get project with locking
            project = (
                self._db.query(Project)
                .filter(Project.project_id == project_id)
                .with_for_update()
                .first()
            )

            if not project:
                return False

            # Delete project
            super().delete(project_id)
            
            # Invalidate caches
            cache.delete_memoized(self.get_by_owner, owner_id)
            cache.delete_memoized(self.validate_owner, owner_id, project_id)
            
            return True
        except Exception as e:
            self._db.rollback()
            raise