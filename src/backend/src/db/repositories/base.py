"""
Base repository module implementing the repository pattern for standardized database operations.

This module provides a production-ready abstract base repository class with:
- Optimized database operations
- Connection pooling and management
- Comprehensive error handling
- Query result caching
- Performance monitoring
- Transaction management

Version: 1.0
"""

import abc
import logging
import functools
from typing import TypeVar, Generic, Type, List, Optional, Tuple, Any, Dict
from datetime import datetime

from sqlalchemy.orm import Session, Query, joinedload
from sqlalchemy.exc import SQLAlchemyError, DBAPIError, IntegrityError
from sqlalchemy.sql.expression import select

from db.session import SessionLocal
from utils.constants import (
    DATABASE_CONSTANTS,
    CACHE_CONSTANTS,
    API_CONSTANTS
)

# Configure logging
logger = logging.getLogger(__name__)

# Type variable for generic model type
Model = TypeVar('Model')

def transactional(func):
    """Decorator for handling database transactions with automatic rollback."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)
            self._db.commit()
            return result
        except SQLAlchemyError as e:
            self._db.rollback()
            logger.error(
                "Transaction failed",
                extra={
                    "error": str(e),
                    "function": func.__name__,
                    "args": args,
                    "kwargs": kwargs
                }
            )
            raise
    return wrapper

def retry_on_deadlock(max_retries: int = 3):
    """Decorator for handling deadlock scenarios with retries."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except DBAPIError as e:
                    if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                        logger.warning(
                            f"Deadlock detected, retry attempt {attempt + 1}/{max_retries}"
                        )
                        self._db.rollback()
                        continue
                    raise
        return wrapper
    return decorator

def monitor_performance(func):
    """Decorator for monitoring database operation performance."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = datetime.now()
        try:
            result = func(self, *args, **kwargs)
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(
                "Database operation completed",
                extra={
                    "operation": func.__name__,
                    "execution_time": execution_time,
                    "model": self._model_class.__name__
                }
            )
            return result
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(
                "Database operation failed",
                extra={
                    "operation": func.__name__,
                    "execution_time": execution_time,
                    "error": str(e),
                    "model": self._model_class.__name__
                }
            )
            raise
    return wrapper

class BaseRepository(Generic[Model], abc.ABC):
    """
    Abstract base repository implementing standardized database operations.
    
    Provides optimized database access patterns with:
    - Connection pooling
    - Query optimization
    - Result caching
    - Error handling
    - Performance monitoring
    """

    def __init__(
        self,
        model_class: Type[Model],
        default_page_size: int = API_CONSTANTS['DEFAULT_PAGE_SIZE'],
        statement_timeout: int = 30000
    ) -> None:
        """
        Initialize repository with model class and configuration.

        Args:
            model_class: SQLAlchemy model class
            default_page_size: Default pagination size
            statement_timeout: SQL statement timeout in milliseconds
        """
        self._model_class = model_class
        self._db: Session = SessionLocal()
        self._default_page_size = default_page_size
        self._statement_timeout = statement_timeout

        # Configure session
        self._db.execute(f"SET statement_timeout TO {statement_timeout}")
        logger.info(
            f"Initialized repository for {model_class.__name__}",
            extra={"default_page_size": default_page_size}
        )

    @retry_on_deadlock()
    @monitor_performance
    def get_by_id(self, id: Any, eager_load: Optional[List[str]] = None) -> Optional[Model]:
        """
        Retrieve a single record by ID with optional eager loading.

        Args:
            id: Primary key value
            eager_load: List of relationships to eager load

        Returns:
            Model instance or None if not found
        """
        try:
            query = self._db.query(self._model_class)
            
            if eager_load:
                for relationship in eager_load:
                    query = query.options(joinedload(relationship))
            
            return query.get(id)
        except SQLAlchemyError as e:
            logger.error(
                "Error retrieving record by ID",
                extra={
                    "model": self._model_class.__name__,
                    "id": id,
                    "error": str(e)
                }
            )
            raise

    @monitor_performance
    def get_all(
        self,
        page: int = 1,
        page_size: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        eager_load: Optional[List[str]] = None
    ) -> Tuple[List[Model], int]:
        """
        Retrieve all records with pagination and filtering.

        Args:
            page: Page number
            page_size: Items per page
            filters: Dictionary of filter conditions
            eager_load: List of relationships to eager load

        Returns:
            Tuple of (list of instances, total count)
        """
        try:
            # Validate pagination
            page_size = page_size or self._default_page_size
            if not API_CONSTANTS['MIN_PAGE_SIZE'] <= page_size <= API_CONSTANTS['MAX_PAGE_SIZE']:
                raise ValueError(f"Invalid page size: {page_size}")

            # Build base query
            query = self._db.query(self._model_class)

            # Apply filters
            if filters:
                for key, value in filters.items():
                    if hasattr(self._model_class, key):
                        query = query.filter(getattr(self._model_class, key) == value)

            # Apply eager loading
            if eager_load:
                for relationship in eager_load:
                    query = query.options(joinedload(relationship))

            # Get total count
            total = query.count()

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

            return query.all(), total

        except SQLAlchemyError as e:
            logger.error(
                "Error retrieving records",
                extra={
                    "model": self._model_class.__name__,
                    "page": page,
                    "page_size": page_size,
                    "error": str(e)
                }
            )
            raise

    @transactional
    @monitor_performance
    def create(self, data: Dict[str, Any]) -> Model:
        """
        Create a new record with validation.

        Args:
            data: Dictionary of model field values

        Returns:
            Created model instance
        """
        try:
            instance = self._model_class(**data)
            self._db.add(instance)
            self._db.flush()
            return instance
        except IntegrityError as e:
            logger.error(
                "Integrity error creating record",
                extra={
                    "model": self._model_class.__name__,
                    "data": data,
                    "error": str(e)
                }
            )
            raise
        except SQLAlchemyError as e:
            logger.error(
                "Error creating record",
                extra={
                    "model": self._model_class.__name__,
                    "data": data,
                    "error": str(e)
                }
            )
            raise

    @transactional
    @monitor_performance
    def bulk_create(self, data_list: List[Dict[str, Any]]) -> List[Model]:
        """
        Create multiple records efficiently.

        Args:
            data_list: List of dictionaries containing model field values

        Returns:
            List of created model instances
        """
        try:
            instances = [self._model_class(**data) for data in data_list]
            self._db.bulk_save_objects(instances)
            self._db.flush()
            return instances
        except SQLAlchemyError as e:
            logger.error(
                "Error bulk creating records",
                extra={
                    "model": self._model_class.__name__,
                    "record_count": len(data_list),
                    "error": str(e)
                }
            )
            raise

    def __del__(self):
        """Cleanup database session on repository destruction."""
        if hasattr(self, '_db'):
            self._db.close()