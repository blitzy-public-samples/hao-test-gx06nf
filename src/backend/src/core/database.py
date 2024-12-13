"""
Core database module for the Specification Management API.

This module provides centralized database connection management with:
- Connection pooling with optimized settings
- Session lifecycle management
- Enhanced monitoring and metrics
- Security features including SSL verification
- High availability support for Cloud SQL
- Performance optimizations

Version: 1.0
"""

import logging
from contextlib import contextmanager
from typing import Generator, Dict, Any, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, DBAPIError, OperationalError

from config.database import DatabaseConfig

# Configure module logger
logger = logging.getLogger(__name__)

# Initialize database engine with pooling configuration
engine = create_engine(
    DatabaseConfig.SQLALCHEMY_DATABASE_URI,
    **DatabaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Create session factory with optimized settings
Session = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

class DatabaseManager:
    """Manages database connections and session lifecycle with enhanced monitoring."""
    
    def __init__(self) -> None:
        """Initialize database manager with monitoring and connection validation."""
        self._engine: Engine = engine
        self._session_factory = Session
        self._pool_metrics: Dict[str, Any] = {
            'total_connections': 0,
            'active_connections': 0,
            'idle_connections': 0,
            'disconnects': 0,
            'timeouts': 0
        }
        
        # Register connection pool event listeners
        event.listen(engine, 'checkout', self._on_checkout)
        event.listen(engine, 'checkin', self._on_checkin)
        event.listen(engine, 'invalidate', self._on_invalidate)

    def get_session(self) -> Session:
        """
        Get a new validated database session.

        Returns:
            Session: Configured SQLAlchemy session

        Raises:
            SQLAlchemyError: If session creation fails
        """
        try:
            session = self._session_factory()
            # Validate connection is active
            session.execute('SELECT 1')
            return session
        except SQLAlchemyError as e:
            logger.error(f"Failed to create database session: {str(e)}")
            raise

    def close_connections(self) -> None:
        """
        Close all database connections with proper cleanup.
        """
        try:
            # Log current pool state
            logger.info(f"Closing connection pool. Current metrics: {self.get_pool_metrics()}")
            
            # Dispose of connection pool
            self._engine.dispose()
            
            # Reset metrics
            self._pool_metrics = {k: 0 for k in self._pool_metrics}
            
            logger.info("Database connections closed successfully")
        except Exception as e:
            logger.error(f"Error closing database connections: {str(e)}")
            raise

    def get_pool_metrics(self) -> Dict[str, Any]:
        """
        Retrieve current connection pool metrics.

        Returns:
            Dict[str, Any]: Pool statistics and health metrics
        """
        return {
            **self._pool_metrics,
            'pool_size': self._engine.pool.size(),
            'checkedin': self._engine.pool.checkedin(),
            'checkedout': self._engine.pool.checkedout(),
            'overflow': self._engine.pool.overflow()
        }

    def _on_checkout(self, dbapi_connection: Any, connection_record: Any, connection_proxy: Any) -> None:
        """Handle connection checkout events for monitoring."""
        self._pool_metrics['active_connections'] += 1
        self._pool_metrics['total_connections'] += 1

    def _on_checkin(self, dbapi_connection: Any, connection_record: Any) -> None:
        """Handle connection checkin events for monitoring."""
        self._pool_metrics['active_connections'] -= 1
        self._pool_metrics['idle_connections'] += 1

    def _on_invalidate(self, dbapi_connection: Any, connection_record: Any, exception: Optional[Exception]) -> None:
        """Handle connection invalidation events for monitoring."""
        self._pool_metrics['disconnects'] += 1
        if isinstance(exception, OperationalError):
            self._pool_metrics['timeouts'] += 1

def get_engine() -> Engine:
    """
    Returns the SQLAlchemy engine instance with configured connection pooling.

    Returns:
        Engine: Configured SQLAlchemy engine instance
    """
    return engine

def get_session() -> Session:
    """
    Creates and returns a new database session with validation.

    Returns:
        Session: Validated new SQLAlchemy session instance

    Raises:
        SQLAlchemyError: If session creation fails
    """
    return DatabaseManager().get_session()

@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Context manager for handling database session lifecycle with enhanced error handling.

    Yields:
        Session: Database session for use within context

    Raises:
        SQLAlchemyError: On database operation failures
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as e:
        logger.error(f"Database error in session: {str(e)}")
        session.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error in database session: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

# Register engine event listeners for connection validation
@event.listens_for(engine, 'connect')
def validate_connection(dbapi_connection: Any, connection_record: Any) -> None:
    """Validate database connection on connect."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute('SELECT 1')
    except Exception as e:
        logger.error(f"Connection validation failed: {str(e)}")
        raise
    finally:
        cursor.close()

@event.listens_for(engine, 'engine_connect')
def ping_connection(connection: Any, branch: bool) -> None:
    """Ping connection before use to ensure it's still valid."""
    if branch:
        return

    try:
        connection.scalar(select([1]))
    except Exception as e:
        logger.warning(f"Connection ping failed: {str(e)}")
        connection.invalidate()
        raise