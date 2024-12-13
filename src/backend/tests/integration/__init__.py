"""
Integration test initialization module for the Specification Management API.

This module configures pytest settings and environment for integration tests with:
- Enhanced database connection pooling and transaction management
- Secure authentication and token validation
- Redis cache configuration for test isolation
- Comprehensive test environment setup and cleanup

Version: 1.0
"""

import os
import pytest
from typing import List, Dict, Any
from datetime import datetime, timedelta
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import TestingConfig
from config.security import SecurityConfig
from config.cache import CACHE_TYPE, CACHE_REDIS_CONFIG
from utils.constants import (
    DATABASE_CONSTANTS,
    AUTH_CONSTANTS,
    CACHE_CONSTANTS
)

# Test Environment Configuration
TEST_ENVIRONMENT: str = "integration"
ENABLE_AUTH_FOR_TESTING: bool = True
ENABLE_DATABASE_FOR_TESTING: bool = True
ENABLE_CACHE_FOR_TESTING: bool = True

# Database Test Configuration
DB_POOL_SIZE: int = 10
DB_POOL_TIMEOUT: int = 30
DB_TEST_URL: str = os.getenv('TEST_DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/spec_mgmt_test')

# Authentication Test Configuration
AUTH_TEST_KEY: str = "test_jwt_secret"
AUTH_TEST_EXPIRY: int = 3600  # 1 hour
AUTH_TEST_ALGORITHM: str = "HS256"

# Cache Test Configuration
REDIS_TEST_HOST: str = os.getenv('TEST_REDIS_HOST', 'localhost')
REDIS_TEST_PORT: int = int(os.getenv('TEST_REDIS_PORT', 6379))
REDIS_TEST_DB: int = 1  # Separate DB for testing

def pytest_configure(config: pytest.Config) -> None:
    """
    Configure pytest settings for integration tests with enhanced security and isolation.

    Args:
        config: pytest configuration object

    This function:
    1. Sets up test environment markers
    2. Configures database connection pool
    3. Sets up authentication for testing
    4. Configures Redis test instance
    5. Establishes test isolation
    """
    # Register integration test marker
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )

    # Configure test database
    if ENABLE_DATABASE_FOR_TESTING:
        # Create test database engine with optimized pooling
        test_engine = create_engine(
            DB_TEST_URL,
            pool_size=DB_POOL_SIZE,
            pool_timeout=DB_POOL_TIMEOUT,
            pool_pre_ping=True,
            echo=False
        )
        
        # Create test session factory
        TestSessionLocal = sessionmaker(
            bind=test_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
        # Add to pytest configuration
        config.test_session_factory = TestSessionLocal
        config.test_engine = test_engine

    # Configure authentication for testing
    if ENABLE_AUTH_FOR_TESTING:
        # Override security settings for testing
        SecurityConfig.JWT_SECRET_KEY = AUTH_TEST_KEY
        SecurityConfig.JWT_ALGORITHM = AUTH_TEST_ALGORITHM
        SecurityConfig.ACCESS_TOKEN_EXPIRE_MINUTES = AUTH_TEST_EXPIRY

    # Configure test cache
    if ENABLE_CACHE_FOR_TESTING:
        # Create isolated Redis test configuration
        test_redis_config = {
            'host': REDIS_TEST_HOST,
            'port': REDIS_TEST_PORT,
            'db': REDIS_TEST_DB,
            'decode_responses': True
        }
        
        # Initialize test Redis client
        test_redis = redis.Redis(**test_redis_config)
        
        # Clear test database before tests
        test_redis.flushdb()
        
        # Add to pytest configuration
        config.test_redis = test_redis

def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    """
    Modify test collection behavior for integration tests with dependency management.

    Args:
        config: pytest configuration object
        items: List of collected test items

    This function:
    1. Adds integration markers
    2. Orders database-dependent tests
    3. Configures test dependencies
    4. Sets up retry mechanisms
    """
    for item in items:
        # Add integration marker to all tests in this directory
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Add database dependency marker if needed
        if ENABLE_DATABASE_FOR_TESTING and "db" in item.keywords:
            item.add_marker(pytest.mark.usefixtures("get_test_db"))

        # Add authentication dependency marker if needed
        if ENABLE_AUTH_FOR_TESTING and "auth" in item.keywords:
            item.add_marker(pytest.mark.usefixtures("auth_headers"))

        # Add cache dependency marker if needed
        if ENABLE_CACHE_FOR_TESTING and "cache" in item.keywords:
            item.add_marker(pytest.mark.usefixtures("test_redis"))

        # Configure retry for flaky tests
        if "flaky" in item.keywords:
            item.add_marker(pytest.mark.flaky(reruns=3, reruns_delay=1))

        # Skip tests if required services are unavailable
        if ENABLE_DATABASE_FOR_TESTING and not _check_database_available():
            if "db" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Database not available"))

        if ENABLE_CACHE_FOR_TESTING and not _check_redis_available():
            if "cache" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Redis not available"))

def _check_database_available() -> bool:
    """
    Check if test database is available.

    Returns:
        bool: True if database is accessible
    """
    try:
        engine = create_engine(DB_TEST_URL)
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False

def _check_redis_available() -> bool:
    """
    Check if test Redis instance is available.

    Returns:
        bool: True if Redis is accessible
    """
    try:
        redis_client = redis.Redis(
            host=REDIS_TEST_HOST,
            port=REDIS_TEST_PORT,
            db=REDIS_TEST_DB
        )
        return redis_client.ping()
    except Exception:
        return False