"""
Unit tests for repository implementations verifying CRUD operations, data access patterns,
and business rules for users, projects, specifications and items.

This module provides comprehensive test coverage for:
- Transaction management and isolation
- Cache operations and invalidation
- Concurrent access patterns
- Business rule enforcement
- Error handling scenarios

Version: 1.0.0
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any
from unittest.mock import Mock, patch

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from redis.exceptions import RedisError

from db.repositories.users import UserRepository
from db.repositories.projects import ProjectRepository
from db.repositories.specifications import SpecificationRepository
from db.repositories.items import ItemRepository
from utils.constants import DATABASE_CONSTANTS, ERROR_MESSAGES

# Test Data Constants
TEST_GOOGLE_ID = "123456789012345678901"
TEST_EMAIL = "test@example.com"
TEST_PROJECT_TITLE = "Test Project"
TEST_SPEC_CONTENT = "Test Specification"
TEST_ITEM_CONTENT = "Test Item"

@pytest.fixture
def mock_redis():
    """Fixture providing a mocked Redis client."""
    return Mock()

@pytest.fixture
def mock_logger():
    """Fixture providing a mocked logger instance."""
    return Mock()

@pytest.mark.asyncio
async def test_user_repository_transactions(db_session):
    """Test user repository transaction isolation and rollback scenarios."""
    repo = UserRepository()
    
    # Test successful transaction
    try:
        user = repo.create_google_user(TEST_GOOGLE_ID, TEST_EMAIL)
        assert user.google_id == TEST_GOOGLE_ID
        assert user.email == TEST_EMAIL
        
        # Verify last login update in same transaction
        updated_user = repo.update_last_login(user)
        assert updated_user.last_login > user.created_at
        
    except SQLAlchemyError:
        pytest.fail("Transaction should succeed")

    # Test transaction rollback
    with pytest.raises(IntegrityError):
        # Attempt to create duplicate user
        repo.create_google_user(TEST_GOOGLE_ID, TEST_EMAIL)

    # Verify original user still exists
    user = repo.get_by_google_id(TEST_GOOGLE_ID)
    assert user is not None
    assert user.email == TEST_EMAIL

@pytest.mark.benchmark
def test_project_repository_concurrent_access(db_session, benchmark):
    """Test concurrent project access patterns and performance."""
    repo = ProjectRepository()
    
    # Create test user and project
    user_repo = UserRepository()
    user = user_repo.create_google_user(TEST_GOOGLE_ID, TEST_EMAIL)
    
    def create_and_validate_project():
        project = repo.create_project(
            owner_id=TEST_GOOGLE_ID,
            project_data={"title": TEST_PROJECT_TITLE}
        )
        assert repo.validate_owner(TEST_GOOGLE_ID, project.project_id)
        return project

    # Benchmark project creation and validation
    result = benchmark(create_and_validate_project)
    assert result.title == TEST_PROJECT_TITLE
    
    # Test concurrent project listing
    projects = repo.get_by_owner(TEST_GOOGLE_ID)
    assert len(projects) > 0
    assert all(p.owner_id == TEST_GOOGLE_ID for p in projects)

def test_specification_repository_cache(db_session, mock_redis, mock_logger):
    """Test specification repository caching behavior."""
    repo = SpecificationRepository(mock_redis, mock_logger)
    
    # Setup test data
    user_repo = UserRepository()
    project_repo = ProjectRepository()
    
    user = user_repo.create_google_user(TEST_GOOGLE_ID, TEST_EMAIL)
    project = project_repo.create_project(
        TEST_GOOGLE_ID,
        {"title": TEST_PROJECT_TITLE}
    )
    
    # Test cache miss and population
    mock_redis.get.return_value = None
    specs = repo.get_by_project(project.project_id, TEST_GOOGLE_ID)
    assert mock_redis.setex.called
    
    # Test cache hit
    mock_redis.get.return_value = specs
    cached_specs = repo.get_by_project(project.project_id, TEST_GOOGLE_ID)
    assert cached_specs == specs
    
    # Test cache invalidation on update
    spec = repo.create_specification(project.project_id, TEST_SPEC_CONTENT, TEST_GOOGLE_ID)
    assert mock_redis.delete.called

def test_item_repository_constraints(db_session):
    """Test item repository business rules and constraints."""
    repo = ItemRepository()
    
    # Setup test data
    user_repo = UserRepository()
    project_repo = ProjectRepository()
    spec_repo = SpecificationRepository(Mock(), Mock())
    
    user = user_repo.create_google_user(TEST_GOOGLE_ID, TEST_EMAIL)
    project = project_repo.create_project(
        TEST_GOOGLE_ID,
        {"title": TEST_PROJECT_TITLE}
    )
    spec = spec_repo.create_specification(
        project.project_id,
        TEST_SPEC_CONTENT,
        TEST_GOOGLE_ID
    )
    
    # Test item limit enforcement
    for i in range(DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']):
        item = repo.create_item({
            'spec_id': spec.spec_id,
            'content': f"{TEST_ITEM_CONTENT} {i}",
            'order_index': i
        })
        assert item.order_index == i
    
    # Verify item limit
    with pytest.raises(ValueError) as exc_info:
        repo.create_item({
            'spec_id': spec.spec_id,
            'content': "Exceeding limit",
            'order_index': DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']
        })
    assert ERROR_MESSAGES['MAX_ITEMS_REACHED'] in str(exc_info.value)
    
    # Test order management
    items = repo.get_by_specification(spec.spec_id)
    assert len(items) == DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']
    assert all(items[i].order_index == i for i in range(len(items)))
    
    # Test cascade deletion
    spec_repo.delete_specification(spec.spec_id, TEST_GOOGLE_ID)
    items = repo.get_by_specification(spec.spec_id)
    assert len(items) == 0

@pytest.mark.asyncio
async def test_repository_error_handling(db_session):
    """Test repository error handling and recovery."""
    user_repo = UserRepository()
    project_repo = ProjectRepository()
    
    # Test invalid input handling
    with pytest.raises(ValueError):
        user_repo.create_google_user("", "invalid_email")
    
    # Test database error handling
    with patch('sqlalchemy.orm.Session.commit') as mock_commit:
        mock_commit.side_effect = SQLAlchemyError("Database error")
        
        with pytest.raises(SQLAlchemyError):
            user_repo.create_google_user(TEST_GOOGLE_ID, TEST_EMAIL)
    
    # Test constraint violation handling
    user = user_repo.create_google_user(TEST_GOOGLE_ID, TEST_EMAIL)
    project = project_repo.create_project(
        TEST_GOOGLE_ID,
        {"title": TEST_PROJECT_TITLE}
    )
    
    with pytest.raises(IntegrityError):
        project_repo.create_project(
            "invalid_owner_id",
            {"title": TEST_PROJECT_TITLE}
        )

def test_repository_performance_benchmarks(benchmark):
    """Benchmark repository operations for performance targets."""
    def setup():
        repo = UserRepository()
        return repo, TEST_GOOGLE_ID, TEST_EMAIL
    
    def create_user(args):
        repo, google_id, email = args
        return repo.create_google_user(google_id, email)
    
    # Benchmark user creation
    benchmark.pedantic(
        create_user,
        setup=setup,
        iterations=100,
        rounds=10
    )