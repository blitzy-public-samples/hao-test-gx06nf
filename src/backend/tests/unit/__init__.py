"""
Unit test initialization module for the Specification Management API.

This module configures pytest settings and environment for unit tests with:
- Optimized test collection and execution
- Security configuration for test environment
- Database connection pooling settings
- Test metrics collection
- Parallel execution optimization

Version: 1.0
"""

import pytest
from typing import List, Dict, Any, Optional
from pytest import Config, Item

# Test environment configuration
TEST_ENVIRONMENT: str = "testing"
DISABLE_AUTH_FOR_TESTING: bool = True
MAX_TEST_POOL_SIZE: int = 5
TEST_DB_TIMEOUT: int = 30

def pytest_configure(config: Config) -> None:
    """
    Configures pytest settings for optimized unit test execution.

    Args:
        config: pytest configuration object

    Configuration includes:
    - Test environment markers
    - Database connection pooling
    - Security parameters
    - Test collection settings
    - Performance optimizations
    """
    # Register custom markers
    config.addinivalue_line(
        "markers",
        "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers",
        "db: mark test as requiring database access"
    )
    config.addinivalue_line(
        "markers",
        "auth: mark test as requiring authentication"
    )

    # Configure test environment
    config.option.env = TEST_ENVIRONMENT
    
    # Set test database configuration
    config.option.database = {
        "pool_size": MAX_TEST_POOL_SIZE,
        "max_overflow": 10,
        "pool_timeout": TEST_DB_TIMEOUT,
        "pool_recycle": 300,  # 5 minutes
        "echo": False  # Disable SQL logging for tests
    }

    # Configure security settings for testing
    config.option.auth = {
        "disable_auth": DISABLE_AUTH_FOR_TESTING,
        "test_token_expiry": 300,  # 5 minutes
        "skip_token_verification": True
    }

    # Configure test collection settings
    config.option.testpaths = ["tests/unit"]
    config.option.python_classes = ["Test*"]
    config.option.python_functions = ["test_*"]
    
    # Enable test metrics collection
    config.option.verbose = 2
    config.option.durations = 10
    config.option.durations_min = 1.0

def pytest_collection_modifyitems(config: Config, items: List[Item]) -> None:
    """
    Modifies test collection for optimized execution order and dependencies.

    Args:
        config: pytest configuration object
        items: List of collected test items

    Modifications include:
    - Adding unit test markers
    - Configuring test dependencies
    - Optimizing execution order
    - Setting up parallel execution
    """
    # Add unit marker to all tests in this directory
    for item in items:
        item.add_marker(pytest.mark.unit)

        # Add database marker for tests requiring DB access
        if "db" in item.keywords or "database" in str(item.function.__doc__):
            item.add_marker(pytest.mark.db)

        # Add auth marker for tests requiring authentication
        if "auth" in item.keywords or "authentication" in str(item.function.__doc__):
            item.add_marker(pytest.mark.auth)

    # Configure test execution order
    items.sort(key=lambda x: (
        # Run independent tests first
        1 if "db" not in x.keywords else 2,
        # Then database tests
        1 if "auth" not in x.keywords else 2,
        # Finally auth-dependent tests
        x.name
    ))

    # Set test dependencies
    for item in items:
        if "db" in item.keywords:
            item.add_marker(pytest.mark.dependency(depends=["db_connection"]))
        if "auth" in item.keywords:
            item.add_marker(pytest.mark.dependency(depends=["auth_setup"]))

    # Configure parallel execution settings
    if config.option.numprocesses:
        # Group tests by dependencies for parallel execution
        db_tests = [item for item in items if "db" in item.keywords]
        auth_tests = [item for item in items if "auth" in item.keywords]
        independent_tests = [item for item in items 
                           if "db" not in item.keywords and "auth" not in item.keywords]

        # Reorder items for optimal parallel execution
        items[:] = independent_tests + db_tests + auth_tests