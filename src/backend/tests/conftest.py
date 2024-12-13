"""
Pytest configuration file providing high-performance test fixtures for database operations,
authentication flows, and common test dependencies.

This module implements:
- Optimized database session fixtures with connection pooling
- Secure JWT token generation for authentication testing
- Test user creation and management
- Automatic cleanup and transaction isolation

Version: 1.0
"""

import pytest
from typing import Generator, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from db.session import Base, get_db
from db.models.users import User
from api.auth.jwt import create_access_token
from config.settings import TestingConfig
from utils.constants import DATABASE_CONSTANTS

# Test user constants
TEST_USER_GOOGLE_ID: str = 'test_google_id_123'
TEST_USER_EMAIL: str = 'test@example.com'

@pytest.fixture
def get_test_db() -> Generator[Session, None, None]:
    """
    Creates and manages a high-performance test database session with proper connection pooling
    and transaction isolation.

    Returns:
        Generator[Session]: SQLAlchemy session configured for high-performance testing
    """
    # Create test database engine with optimized pooling
    engine = create_engine(
        TestingConfig.SQLALCHEMY_DATABASE_URI,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=20,
        pool_timeout=30,
        pool_pre_ping=True,
        echo=False
    )

    # Create all tables in test database
    Base.metadata.create_all(bind=engine)

    # Create session factory with performance settings
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=True,  # Enable autoflush for immediate constraint checking
        expire_on_commit=False  # Prevent detached instance errors
    )

    # Create and yield test session
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        # Rollback any pending transactions
        session.rollback()
        # Close session
        session.close()
        # Drop all tables for cleanup
        Base.metadata.drop_all(bind=engine)
        # Dispose engine connections
        engine.dispose()

@pytest.fixture
def test_user(get_test_db: Session) -> User:
    """
    Creates a test user instance with proper authentication data for testing.

    Args:
        get_test_db (Session): Test database session

    Returns:
        User: Configured test user instance with authentication data
    """
    # Create test user instance
    user = User(
        google_id=TEST_USER_GOOGLE_ID,
        email=TEST_USER_EMAIL
    )

    try:
        # Add and commit user to database
        get_test_db.add(user)
        get_test_db.flush()  # Validate constraints
        get_test_db.commit()
        # Refresh to ensure all attributes are loaded
        get_test_db.refresh(user)
        return user
    except Exception as e:
        get_test_db.rollback()
        raise pytest.fail(f"Failed to create test user: {str(e)}")

@pytest.fixture
def auth_headers(test_user: User) -> Dict[str, str]:
    """
    Generates secure authentication headers with JWT token for testing.

    Args:
        test_user (User): Test user instance

    Returns:
        Dict[str, str]: HTTP headers dictionary containing Bearer token
    """
    # Create access token with test user data
    token = create_access_token(
        data={
            "sub": test_user.google_id,
            "email": test_user.email
        }
    )

    # Return headers with Bearer token
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }