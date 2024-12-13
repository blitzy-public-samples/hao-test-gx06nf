"""
Database initialization module for the Specification Management API.

This module configures and exports essential database components including:
- SQLAlchemy session management
- Base model configuration
- Connection pooling setup
- Thread-safe session handling
- Database initialization utilities

Version: 1.0.0
SQLAlchemy Version: 1.4.x
"""

from typing import Generator
import logging

# Import core database components
from .base import Base
from .session import db_session, get_db

# Configure module logger
logger = logging.getLogger(__name__)

def init_db() -> None:
    """
    Initialize database schema and create tables if they don't exist.
    This should be called during application startup.
    
    Note: Models are imported in base.py to prevent circular imports
    """
    try:
        # Create all tables defined in the models
        Base.metadata.create_all(bind=db_session.get_bind())
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {str(e)}")
        raise

def cleanup_db() -> None:
    """
    Cleanup database connections and resources.
    This should be called during application shutdown.
    """
    try:
        db_session.remove()
        logger.info("Database session cleanup completed")
    except Exception as e:
        logger.error(f"Error during database cleanup: {str(e)}")
        raise

def get_db_session() -> Generator:
    """
    Get a thread-safe database session with proper error handling and cleanup.
    
    Yields:
        SQLAlchemy session: Thread-local session instance
        
    Example:
        with get_db_session() as session:
            session.query(User).all()
    """
    try:
        yield db_session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db_session.rollback()
        raise
    finally:
        db_session.remove()

# Export essential database components
__all__ = [
    'Base',           # SQLAlchemy declarative base
    'db_session',     # Thread-safe session factory
    'get_db',         # FastAPI dependency injection function
    'init_db',        # Database initialization function
    'cleanup_db',     # Database cleanup function
    'get_db_session'  # Session context manager
]

# Module initialization logging
logger.info("Database module initialized with connection pooling (size: 10-100, timeout: 30s)")