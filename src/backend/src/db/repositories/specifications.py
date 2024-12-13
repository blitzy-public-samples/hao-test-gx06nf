"""
Repository implementation for managing specifications with enhanced transaction management,
caching, and optimized query patterns. Handles CRUD operations, ordering, and bulk operations
for specifications within projects.

Version: 1.0.0
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import and_, func, select, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from redis import Redis
from redis.exceptions import RedisError

from .base import BaseRepository
from ..models.specifications import Specification
from ..models.projects import Project
from ...utils.constants import (
    DATABASE_CONSTANTS,
    CACHE_CONSTANTS,
    ERROR_MESSAGES
)

class SpecificationRepository(BaseRepository[Specification]):
    """
    Enhanced repository for managing specifications with optimized queries,
    caching, and transaction management.
    """

    def __init__(self, cache_client: Redis, logger: logging.Logger) -> None:
        """
        Initialize specifications repository with caching and logging support.

        Args:
            cache_client: Redis client for caching
            logger: Logger instance for monitoring and debugging
        """
        super().__init__(Specification)
        self._cache_client = cache_client
        self._logger = logger
        self._cache_prefix = f"{CACHE_CONSTANTS['CACHE_KEY_PREFIX']}_spec"

    def get_by_project(
        self,
        project_id: int,
        owner_id: str,
        use_cache: bool = True
    ) -> List[Specification]:
        """
        Retrieve all specifications for a project with caching and ownership validation.

        Args:
            project_id: ID of the project
            owner_id: Google ID of the project owner
            use_cache: Whether to use cache (default: True)

        Returns:
            List[Specification]: Ordered list of specifications

        Raises:
            ValueError: If project_id is invalid
            PermissionError: If user doesn't own the project
        """
        try:
            # Check cache first if enabled
            if use_cache:
                cache_key = f"{self._cache_prefix}:project:{project_id}"
                cached_data = self._get_from_cache(cache_key)
                if cached_data:
                    self._logger.debug(f"Cache hit for project specifications: {project_id}")
                    return cached_data

            # Verify project ownership
            project = self._db.query(Project).filter(
                and_(
                    Project.project_id == project_id,
                    Project.owner_id == owner_id
                )
            ).first()

            if not project:
                raise PermissionError(ERROR_MESSAGES['PROJECT_ACCESS_DENIED'])

            # Query specifications with optimized loading
            specifications = self._db.query(Specification).filter(
                Specification.project_id == project_id
            ).order_by(
                Specification.order_index
            ).options(
                joinedload(Specification.items)
            ).all()

            # Cache results if enabled
            if use_cache:
                self._cache_results(
                    f"{self._cache_prefix}:project:{project_id}",
                    specifications,
                    CACHE_CONSTANTS['SPECIFICATION_CACHE_TTL']
                )

            return specifications

        except SQLAlchemyError as e:
            self._logger.error(
                "Database error in get_by_project",
                extra={
                    "project_id": project_id,
                    "error": str(e)
                }
            )
            raise

    def create_specification(
        self,
        project_id: int,
        content: str,
        owner_id: str
    ) -> Specification:
        """
        Create a new specification with transaction management and cache invalidation.

        Args:
            project_id: ID of the parent project
            content: Specification content
            owner_id: Google ID of the project owner

        Returns:
            Specification: Created specification instance

        Raises:
            ValueError: If validation fails
            PermissionError: If user doesn't own the project
            SQLAlchemyError: If database constraints are violated
        """
        try:
            # Start transaction
            self._db.begin_nested()

            # Verify project ownership
            project = self._db.query(Project).filter(
                and_(
                    Project.project_id == project_id,
                    Project.owner_id == owner_id
                )
            ).with_for_update().first()

            if not project:
                raise PermissionError(ERROR_MESSAGES['PROJECT_ACCESS_DENIED'])

            # Get current max order_index
            max_order = self._db.query(
                func.coalesce(func.max(Specification.order_index), -1)
            ).filter(
                Specification.project_id == project_id
            ).scalar()

            # Create specification
            specification = Specification(
                project_id=project_id,
                content=content,
                order_index=max_order + 1
            )

            self._db.add(specification)
            self._db.flush()

            # Invalidate cache
            self._invalidate_project_cache(project_id)

            # Commit transaction
            self._db.commit()
            return specification

        except SQLAlchemyError as e:
            self._db.rollback()
            self._logger.error(
                "Database error in create_specification",
                extra={
                    "project_id": project_id,
                    "error": str(e)
                }
            )
            raise

    def update_order(
        self,
        spec_id: int,
        new_order_index: int,
        owner_id: str
    ) -> bool:
        """
        Update specification order with transaction isolation and cache management.

        Args:
            spec_id: ID of the specification to reorder
            new_order_index: New position in the order
            owner_id: Google ID of the project owner

        Returns:
            bool: Success status

        Raises:
            ValueError: If order index is invalid
            PermissionError: If user doesn't own the project
        """
        try:
            # Start transaction with REPEATABLE READ isolation
            self._db.begin_nested()

            # Get specification with project ownership check
            spec = self._db.query(Specification).join(
                Project
            ).filter(
                and_(
                    Specification.spec_id == spec_id,
                    Project.owner_id == owner_id
                )
            ).with_for_update().first()

            if not spec:
                raise PermissionError(ERROR_MESSAGES['UNAUTHORIZED_ACCESS'])

            # Update order
            old_order = spec.order_index
            spec.reorder(new_order_index)

            # Reorder other specifications
            if new_order_index > old_order:
                self._db.query(Specification).filter(
                    and_(
                        Specification.project_id == spec.project_id,
                        Specification.order_index <= new_order_index,
                        Specification.order_index > old_order,
                        Specification.spec_id != spec_id
                    )
                ).update(
                    {"order_index": Specification.order_index - 1}
                )
            else:
                self._db.query(Specification).filter(
                    and_(
                        Specification.project_id == spec.project_id,
                        Specification.order_index >= new_order_index,
                        Specification.order_index < old_order,
                        Specification.spec_id != spec_id
                    )
                ).update(
                    {"order_index": Specification.order_index + 1}
                )

            # Invalidate cache
            self._invalidate_project_cache(spec.project_id)

            # Commit transaction
            self._db.commit()
            return True

        except SQLAlchemyError as e:
            self._db.rollback()
            self._logger.error(
                "Database error in update_order",
                extra={
                    "spec_id": spec_id,
                    "error": str(e)
                }
            )
            raise

    def delete_specification(self, spec_id: int, owner_id: str) -> bool:
        """
        Delete specification with cascade and reordering.

        Args:
            spec_id: ID of the specification to delete
            owner_id: Google ID of the project owner

        Returns:
            bool: Success status

        Raises:
            PermissionError: If user doesn't own the project
        """
        try:
            # Start transaction
            self._db.begin_nested()

            # Get specification with project ownership check
            spec = self._db.query(Specification).join(
                Project
            ).filter(
                and_(
                    Specification.spec_id == spec_id,
                    Project.owner_id == owner_id
                )
            ).with_for_update().first()

            if not spec:
                raise PermissionError(ERROR_MESSAGES['UNAUTHORIZED_ACCESS'])

            project_id = spec.project_id
            order_index = spec.order_index

            # Delete specification (cascade will handle items)
            self._db.delete(spec)

            # Reorder remaining specifications
            self._db.query(Specification).filter(
                and_(
                    Specification.project_id == project_id,
                    Specification.order_index > order_index
                )
            ).update(
                {"order_index": Specification.order_index - 1}
            )

            # Invalidate caches
            self._invalidate_project_cache(project_id)

            # Commit transaction
            self._db.commit()
            return True

        except SQLAlchemyError as e:
            self._db.rollback()
            self._logger.error(
                "Database error in delete_specification",
                extra={
                    "spec_id": spec_id,
                    "error": str(e)
                }
            )
            raise

    def _invalidate_project_cache(self, project_id: int) -> None:
        """
        Invalidate cache entries for a project's specifications.

        Args:
            project_id: ID of the project to invalidate
        """
        try:
            cache_key = f"{self._cache_prefix}:project:{project_id}"
            self._cache_client.delete(cache_key)
        except RedisError as e:
            self._logger.warning(
                "Cache invalidation failed",
                extra={
                    "project_id": project_id,
                    "error": str(e)
                }
            )

    def _get_from_cache(self, cache_key: str) -> Optional[List[Specification]]:
        """
        Retrieve specifications from cache with error handling.

        Args:
            cache_key: Cache key to retrieve

        Returns:
            Optional[List[Specification]]: Cached specifications or None
        """
        try:
            return self._cache_client.get(cache_key)
        except RedisError as e:
            self._logger.warning(
                "Cache retrieval failed",
                extra={
                    "cache_key": cache_key,
                    "error": str(e)
                }
            )
            return None

    def _cache_results(
        self,
        cache_key: str,
        data: List[Specification],
        ttl: int
    ) -> None:
        """
        Cache specification results with error handling.

        Args:
            cache_key: Cache key to store
            data: Specifications to cache
            ttl: Time-to-live in seconds
        """
        try:
            self._cache_client.setex(
                cache_key,
                ttl,
                data
            )
        except RedisError as e:
            self._logger.warning(
                "Cache storage failed",
                extra={
                    "cache_key": cache_key,
                    "error": str(e)
                }
            )