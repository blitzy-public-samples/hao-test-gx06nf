"""
Database session management module for the Specification Management API.

This module provides a production-ready SQLAlchemy session factory and connection
management system with:
- Optimized connection pooling
- Connection health monitoring
- Enhanced error handling
- Automatic connection recycling
- SSL support for production
- Comprehensive logging

Version: 1.0
"""

import logging
from typing import Generator
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError

from config.database import DatabaseConfig

# Configure logging
logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with production-ready configuration
engine = create_engine(
    DatabaseConfig.SQLALCHEMY_DATABASE_URI,
    **DatabaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
    # Enable connection health checks
    pool_pre_ping=True,
    # Recycle connections every hour to prevent stale connections
    pool_recycle=3600
)

# Create session factory with optimized settings
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    # Prevent detached instance errors
    expire_on_commit=False
)

# Create declarative base for models
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that yields database sessions with enhanced error handling
    and connection verification.
    
    Yields:
        Session: SQLAlchemy session instance with verified connection
    
    Raises:
        SQLAlchemyError: If database connection or operation fails
    """
    session = SessionLocal()
    try:
        # Verify connection with lightweight query
        session.execute(select(1))
        logger.debug(
            "Database session established",
            extra={
                "engine_id": engine.pool.logging_name,
                "pool_size": engine.pool.size(),
                "checkedin": engine.pool.checkedin(),
                "overflow": engine.pool.overflow()
            }
        )
        yield session
    except SQLAlchemyError as e:
        logger.error(
            "Database session error",
            extra={
                "error": str(e),
                "engine_id": engine.pool.logging_name
            }
        )
        # Ensure transaction is rolled back
        session.rollback()
        raise
    finally:
        # Guarantee session cleanup
        session.close()
        logger.debug(
            "Database session closed",
            extra={
                "engine_id": engine.pool.logging_name,
                "pool_size": engine.pool.size()
            }
        )

# Export database components
__all__ = ['Base', 'engine', 'SessionLocal', 'get_db']