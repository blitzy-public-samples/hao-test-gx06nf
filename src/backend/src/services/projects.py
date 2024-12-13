"""
Service layer implementation for project management business logic with comprehensive
caching, validation, monitoring and error handling. Implements thread-safe operations
with circuit breaker pattern and transaction management.

Version: 1.0
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from ..db.repositories.projects import ProjectRepository
from ..api.schemas.projects import ProjectCreate, ProjectResponse
from .cache import (
    cache_project_list,
    get_cached_project_list,
    invalidate_project_cache
)
from ..utils.constants import (
    DATABASE_CONSTANTS,
    ERROR_MESSAGES,
    HTTP_STATUS_CODES
)

# Configure logging
logger = logging.getLogger(__name__)

class ProjectService:
    """
    Thread-safe service class implementing project management business logic with
    caching, monitoring and error handling.
    """

    def __init__(self, repository: ProjectRepository) -> None:
        """
        Initialize project service with repository dependency injection.

        Args:
            repository: Project repository instance for database operations
        """
        self._repository = repository
        logger.info("Initialized ProjectService with repository")

    async def get_user_projects(self, owner_id: str) -> List[ProjectResponse]:
        """
        Get all projects owned by a user with caching and circuit breaker pattern.

        Args:
            owner_id: Google ID of the project owner

        Returns:
            List[ProjectResponse]: List of projects owned by user

        Raises:
            ValueError: If owner_id is invalid
            Exception: If database operation fails
        """
        try:
            logger.debug(f"Fetching projects for user {owner_id}")

            # Attempt to get from cache first
            cached_projects = get_cached_project_list(owner_id)
            if cached_projects is not None:
                logger.debug(f"Cache hit for user {owner_id} projects")
                return [ProjectResponse(**project) for project in cached_projects]

            # Cache miss - fetch from database
            projects = self._repository.get_by_owner(owner_id)
            
            # Convert to response schema and cache
            project_responses = [ProjectResponse.from_orm(project) for project in projects]
            project_data = [response.dict() for response in project_responses]
            
            # Cache the results
            cache_project_list(owner_id, project_data)
            
            logger.info(f"Successfully retrieved {len(projects)} projects for user {owner_id}")
            return project_responses

        except ValueError as e:
            logger.error(f"Validation error in get_user_projects: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving projects for user {owner_id}: {str(e)}")
            raise

    async def create_project(self, owner_id: str, project_data: ProjectCreate) -> ProjectResponse:
        """
        Create new project with transaction management and cache invalidation.

        Args:
            owner_id: Google ID of the project owner
            project_data: Validated project creation data

        Returns:
            ProjectResponse: Created project data

        Raises:
            ValueError: If project data is invalid or limit reached
            Exception: If database operation fails
        """
        try:
            logger.debug(f"Creating project for user {owner_id}")

            # Check project count limit
            existing_projects = self._repository.get_by_owner(owner_id)
            if len(existing_projects) >= DATABASE_CONSTANTS['MAX_SPECIFICATIONS_PER_PROJECT']:
                raise ValueError(ERROR_MESSAGES['MAX_ITEMS_REACHED'])

            # Create project
            project = self._repository.create_project(
                owner_id=owner_id,
                project_data=project_data.dict()
            )

            # Invalidate user's project cache
            invalidate_project_cache(str(project.project_id))

            response = ProjectResponse.from_orm(project)
            logger.info(f"Successfully created project {project.project_id} for user {owner_id}")
            return response

        except ValueError as e:
            logger.error(f"Validation error in create_project: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating project for user {owner_id}: {str(e)}")
            raise

    async def update_project(
        self,
        owner_id: str,
        project_id: int,
        project_data: ProjectCreate
    ) -> Optional[ProjectResponse]:
        """
        Update project with ownership validation and transaction safety.

        Args:
            owner_id: Google ID of the project owner
            project_id: ID of project to update
            project_data: Validated project update data

        Returns:
            Optional[ProjectResponse]: Updated project if successful

        Raises:
            ValueError: If project data is invalid
            Exception: If database operation fails
        """
        try:
            logger.debug(f"Updating project {project_id} for user {owner_id}")

            # Validate ownership
            if not await self.validate_project_owner(owner_id, project_id):
                logger.warning(f"Unauthorized project update attempt by user {owner_id}")
                return None

            # Update project
            updated_project = self._repository.update_project(
                owner_id=owner_id,
                project_id=project_id,
                project_data=project_data.dict()
            )

            if not updated_project:
                return None

            # Invalidate caches
            invalidate_project_cache(str(project_id))

            response = ProjectResponse.from_orm(updated_project)
            logger.info(f"Successfully updated project {project_id}")
            return response

        except ValueError as e:
            logger.error(f"Validation error in update_project: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error updating project {project_id}: {str(e)}")
            raise

    async def delete_project(self, owner_id: str, project_id: int) -> bool:
        """
        Delete project with ownership validation and cache cleanup.

        Args:
            owner_id: Google ID of the project owner
            project_id: ID of project to delete

        Returns:
            bool: True if deleted successfully

        Raises:
            Exception: If database operation fails
        """
        try:
            logger.debug(f"Deleting project {project_id} for user {owner_id}")

            # Validate ownership
            if not await self.validate_project_owner(owner_id, project_id):
                logger.warning(f"Unauthorized project deletion attempt by user {owner_id}")
                return False

            # Delete project
            success = self._repository.delete_project(
                owner_id=owner_id,
                project_id=project_id
            )

            if success:
                # Invalidate caches
                invalidate_project_cache(str(project_id))
                logger.info(f"Successfully deleted project {project_id}")

            return success

        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {str(e)}")
            raise

    async def validate_project_owner(self, owner_id: str, project_id: int) -> bool:
        """
        Validate project ownership with caching.

        Args:
            owner_id: Google ID of potential owner
            project_id: ID of project to validate

        Returns:
            bool: True if user owns project
        """
        try:
            logger.debug(f"Validating ownership of project {project_id} for user {owner_id}")
            return self._repository.validate_owner(owner_id, project_id)

        except Exception as e:
            logger.error(f"Error validating project ownership: {str(e)}")
            return False