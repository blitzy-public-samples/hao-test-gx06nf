"""
Service layer implementation for managing specifications within projects.
Provides comprehensive business logic for CRUD operations, ordering,
caching, and validation with production-ready features.

Version: 1.0.0
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from functools import wraps

from prometheus_client import Counter, Histogram
from circuitbreaker import circuit

from db.repositories.specifications import SpecificationRepository
from db.models.specifications import Specification
from services.cache import (
    cache_specifications,
    get_cached_specifications,
    invalidate_specification_cache
)
from utils.constants import (
    DATABASE_CONSTANTS,
    CACHE_CONSTANTS,
    ERROR_MESSAGES
)

# Configure logging
logger = logging.getLogger(__name__)

# Constants
CACHE_TTL_SECONDS = CACHE_CONSTANTS['SPECIFICATION_CACHE_TTL']
MAX_RETRY_ATTEMPTS = 3
BATCH_SIZE = 100

def monitor_performance(func):
    """Decorator for monitoring service operation performance."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = datetime.now(timezone.utc)
        try:
            result = func(self, *args, **kwargs)
            self._operation_latency.observe(
                (datetime.now(timezone.utc) - start_time).total_seconds()
            )
            return result
        except Exception as e:
            logger.error(
                f"Operation failed: {func.__name__}",
                extra={
                    "error": str(e),
                    "args": args,
                    "kwargs": kwargs
                }
            )
            raise
    return wrapper

class SpecificationService:
    """
    Service class providing business logic for specification management with
    enhanced error handling, monitoring, and performance optimizations.
    """

    def __init__(self) -> None:
        """Initialize service with monitoring and repository setup."""
        self._repository = SpecificationRepository()
        
        # Initialize monitoring metrics
        self._cache_hits = Counter(
            'specification_cache_hits_total',
            'Number of specification cache hits'
        )
        self._cache_misses = Counter(
            'specification_cache_misses_total',
            'Number of specification cache misses'
        )
        self._operation_latency = Histogram(
            'specification_operation_duration_seconds',
            'Duration of specification operations'
        )

    @circuit(failure_threshold=5, recovery_timeout=60)
    @monitor_performance
    def get_project_specifications(
        self,
        project_id: int,
        owner_id: str,
        use_cache: bool = True
    ) -> List[Specification]:
        """
        Retrieve all specifications for a project with caching and monitoring.

        Args:
            project_id: Project identifier
            owner_id: Project owner's Google ID
            use_cache: Whether to use cache (default: True)

        Returns:
            List[Specification]: Ordered list of specifications

        Raises:
            ValueError: If project_id is invalid
            PermissionError: If user doesn't own the project
        """
        try:
            # Validate inputs
            if not isinstance(project_id, int) or project_id <= 0:
                raise ValueError("Invalid project ID")

            # Check cache if enabled
            if use_cache:
                cached_specs = get_cached_specifications(str(project_id))
                if cached_specs is not None:
                    self._cache_hits.inc()
                    logger.debug(f"Cache hit for project specifications: {project_id}")
                    return cached_specs

            self._cache_misses.inc()
            
            # Get specifications from repository
            specifications = self._repository.get_by_project(
                project_id=project_id,
                owner_id=owner_id
            )

            # Cache results if enabled
            if use_cache and specifications:
                cache_specifications(str(project_id), specifications)

            return specifications

        except Exception as e:
            logger.error(
                "Error retrieving project specifications",
                extra={
                    "project_id": project_id,
                    "owner_id": owner_id,
                    "error": str(e)
                }
            )
            raise

    @monitor_performance
    def create_specification(
        self,
        project_id: int,
        content: str,
        owner_id: str
    ) -> Specification:
        """
        Create a new specification with validation and error handling.

        Args:
            project_id: Project identifier
            content: Specification content
            owner_id: Project owner's Google ID

        Returns:
            Specification: Created specification instance

        Raises:
            ValueError: If validation fails
            PermissionError: If user doesn't own the project
        """
        try:
            # Validate content length
            if not content or len(content) > DATABASE_CONSTANTS['MAX_CONTENT_LENGTH']:
                raise ValueError(
                    f"Content length must be between 1 and "
                    f"{DATABASE_CONSTANTS['MAX_CONTENT_LENGTH']} characters"
                )

            # Create specification
            specification = self._repository.create_specification(
                project_id=project_id,
                content=content,
                owner_id=owner_id
            )

            # Invalidate project specifications cache
            invalidate_specification_cache(str(project_id))

            logger.info(
                f"Created specification {specification.spec_id} "
                f"for project {project_id}"
            )
            return specification

        except Exception as e:
            logger.error(
                "Error creating specification",
                extra={
                    "project_id": project_id,
                    "owner_id": owner_id,
                    "error": str(e)
                }
            )
            raise

    @monitor_performance
    def update_specification_order(
        self,
        spec_id: int,
        new_order_index: int,
        owner_id: str
    ) -> bool:
        """
        Update specification order with optimistic locking.

        Args:
            spec_id: Specification identifier
            new_order_index: New position in order
            owner_id: Project owner's Google ID

        Returns:
            bool: Success status

        Raises:
            ValueError: If order index is invalid
            PermissionError: If user doesn't own the project
        """
        try:
            # Validate order index
            if not 0 <= new_order_index <= DATABASE_CONSTANTS['MAX_ORDER_INDEX']:
                raise ValueError(ERROR_MESSAGES['INVALID_ORDER_INDEX'])

            # Update order with retry mechanism
            for attempt in range(MAX_RETRY_ATTEMPTS):
                try:
                    success = self._repository.update_order(
                        spec_id=spec_id,
                        new_order_index=new_order_index,
                        owner_id=owner_id
                    )
                    
                    if success:
                        # Get specification's project ID for cache invalidation
                        spec = self._repository.get_by_id(spec_id)
                        if spec:
                            invalidate_specification_cache(str(spec.project_id))
                        
                        logger.info(
                            f"Updated order for specification {spec_id} "
                            f"to {new_order_index}"
                        )
                        return True
                    
                    return False

                except Exception as e:
                    if attempt == MAX_RETRY_ATTEMPTS - 1:
                        raise
                    logger.warning(
                        f"Retry attempt {attempt + 1} for order update",
                        extra={"spec_id": spec_id, "error": str(e)}
                    )

        except Exception as e:
            logger.error(
                "Error updating specification order",
                extra={
                    "spec_id": spec_id,
                    "new_order_index": new_order_index,
                    "error": str(e)
                }
            )
            raise

    @monitor_performance
    def delete_specification(self, spec_id: int, owner_id: str) -> bool:
        """
        Delete specification with cascade handling.

        Args:
            spec_id: Specification identifier
            owner_id: Project owner's Google ID

        Returns:
            bool: Success status

        Raises:
            PermissionError: If user doesn't own the project
        """
        try:
            # Get specification's project ID before deletion for cache invalidation
            spec = self._repository.get_by_id(spec_id)
            project_id = spec.project_id if spec else None

            # Delete specification
            success = self._repository.delete_specification(
                spec_id=spec_id,
                owner_id=owner_id
            )

            if success and project_id:
                # Invalidate caches
                invalidate_specification_cache(str(project_id))
                logger.info(f"Deleted specification {spec_id}")
                return True

            return False

        except Exception as e:
            logger.error(
                "Error deleting specification",
                extra={
                    "spec_id": spec_id,
                    "error": str(e)
                }
            )
            raise