"""
Integration tests for project management endpoints.
Tests project CRUD operations, authentication, authorization, and performance requirements.

Version: 1.0
"""

import time
import pytest
from typing import Dict, Any
from http import HTTPStatus

from src.db.models.projects import Project
from src.utils.constants import (
    DATABASE_CONSTANTS,
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    API_CONSTANTS
)

# Test constants
PROJECTS_URL = '/api/v1/projects'
TEST_PROJECT_TITLE = 'Test Project'
RESPONSE_TIME_LIMIT = 0.5  # 500ms performance requirement

@pytest.mark.integration
def test_create_project(db_session: Any, test_client: Any, auth_headers: Dict[str, str]) -> None:
    """
    Test successful project creation with valid data and performance requirements.
    
    Args:
        db_session: SQLAlchemy database session fixture
        test_client: Flask test client fixture
        auth_headers: Authenticated request headers fixture
    """
    # Prepare test data
    project_data = {
        'title': TEST_PROJECT_TITLE
    }

    # Measure response time
    start_time = time.time()
    response = test_client.post(
        PROJECTS_URL,
        json=project_data,
        headers=auth_headers
    )
    response_time = time.time() - start_time

    # Assert performance requirement
    assert response_time < RESPONSE_TIME_LIMIT, f"Response time {response_time}s exceeded limit of {RESPONSE_TIME_LIMIT}s"

    # Assert response status and format
    assert response.status_code == HTTP_STATUS_CODES['CREATED']
    response_data = response.get_json()
    assert 'data' in response_data
    assert 'project_id' in response_data['data']

    # Verify database state
    project = db_session.query(Project).filter_by(
        project_id=response_data['data']['project_id']
    ).first()
    assert project is not None
    assert project.title == TEST_PROJECT_TITLE
    assert project.owner_id == auth_headers['X-User-ID']
    assert project.created_at is not None
    assert project.updated_at is not None

@pytest.mark.integration
def test_get_user_projects(db_session: Any, test_client: Any, auth_headers: Dict[str, str]) -> None:
    """
    Test retrieving all projects for authenticated user with pagination and sorting.
    
    Args:
        db_session: SQLAlchemy database session fixture
        test_client: Flask test client fixture
        auth_headers: Authenticated request headers fixture
    """
    # Create test projects
    projects = []
    for i in range(3):
        project = Project(
            title=f"{TEST_PROJECT_TITLE}_{i}",
            owner_id=auth_headers['X-User-ID']
        )
        db_session.add(project)
    db_session.commit()

    # Test pagination and sorting
    params = {
        'page': 1,
        'per_page': API_CONSTANTS['DEFAULT_PAGE_SIZE'],
        'sort': 'created_at',
        'order': API_CONSTANTS['DEFAULT_SORT_ORDER']
    }

    # Measure response time
    start_time = time.time()
    response = test_client.get(
        PROJECTS_URL,
        query_string=params,
        headers=auth_headers
    )
    response_time = time.time() - start_time

    # Assert performance requirement
    assert response_time < RESPONSE_TIME_LIMIT

    # Assert response
    assert response.status_code == HTTP_STATUS_CODES['OK']
    response_data = response.get_json()
    
    assert 'data' in response_data
    assert 'items' in response_data['data']
    assert 'metadata' in response_data['data']
    assert len(response_data['data']['items']) == 3
    
    # Verify sorting
    items = response_data['data']['items']
    assert all(items[i]['created_at'] <= items[i+1]['created_at'] 
              for i in range(len(items)-1))

@pytest.mark.integration
def test_update_project(db_session: Any, test_client: Any, auth_headers: Dict[str, str]) -> None:
    """
    Test project update with valid data, owner authentication, and timestamp verification.
    
    Args:
        db_session: SQLAlchemy database session fixture
        test_client: Flask test client fixture
        auth_headers: Authenticated request headers fixture
    """
    # Create test project
    project = Project(
        title=TEST_PROJECT_TITLE,
        owner_id=auth_headers['X-User-ID']
    )
    db_session.add(project)
    db_session.commit()
    
    initial_updated_at = project.updated_at
    
    # Update project
    update_data = {
        'title': f"{TEST_PROJECT_TITLE}_updated"
    }
    
    # Measure response time
    start_time = time.time()
    response = test_client.put(
        f"{PROJECTS_URL}/{project.project_id}",
        json=update_data,
        headers=auth_headers
    )
    response_time = time.time() - start_time

    # Assert performance requirement
    assert response_time < RESPONSE_TIME_LIMIT

    # Assert response
    assert response.status_code == HTTP_STATUS_CODES['OK']
    
    # Verify database update
    db_session.refresh(project)
    assert project.title == update_data['title']
    assert project.updated_at > initial_updated_at

@pytest.mark.integration
def test_delete_project(db_session: Any, test_client: Any, auth_headers: Dict[str, str]) -> None:
    """
    Test project deletion with owner authentication and cascade verification.
    
    Args:
        db_session: SQLAlchemy database session fixture
        test_client: Flask test client fixture
        auth_headers: Authenticated request headers fixture
    """
    # Create test project
    project = Project(
        title=TEST_PROJECT_TITLE,
        owner_id=auth_headers['X-User-ID']
    )
    db_session.add(project)
    db_session.commit()
    
    project_id = project.project_id

    # Measure response time
    start_time = time.time()
    response = test_client.delete(
        f"{PROJECTS_URL}/{project_id}",
        headers=auth_headers
    )
    response_time = time.time() - start_time

    # Assert performance requirement
    assert response_time < RESPONSE_TIME_LIMIT

    # Assert response
    assert response.status_code == HTTP_STATUS_CODES['NO_CONTENT']
    
    # Verify database deletion
    deleted_project = db_session.query(Project).filter_by(
        project_id=project_id
    ).first()
    assert deleted_project is None

@pytest.mark.integration
def test_unauthorized_access(db_session: Any, test_client: Any) -> None:
    """
    Test unauthorized access to project operations with rate limiting.
    
    Args:
        db_session: SQLAlchemy database session fixture
        test_client: Flask test client fixture
    """
    # Test project creation without auth
    project_data = {
        'title': TEST_PROJECT_TITLE
    }
    
    response = test_client.post(
        PROJECTS_URL,
        json=project_data
    )
    
    assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']
    error_data = response.get_json()
    assert 'error' in error_data
    assert error_data['error']['message'] == ERROR_MESSAGES['INVALID_TOKEN']

    # Test rate limiting
    for _ in range(RATE_LIMIT_CONSTANTS['BURST_LIMIT'] + 1):
        response = test_client.post(PROJECTS_URL, json=project_data)
        if response.status_code == HTTP_STATUS_CODES['RATE_LIMITED']:
            break
    
    assert response.status_code == HTTP_STATUS_CODES['RATE_LIMITED']

@pytest.mark.integration
def test_project_owner_authorization(
    db_session: Any,
    test_client: Any,
    auth_headers: Dict[str, str]
) -> None:
    """
    Test project operations with non-owner authentication scenarios.
    
    Args:
        db_session: SQLAlchemy database session fixture
        test_client: Flask test client fixture
        auth_headers: Authenticated request headers fixture
    """
    # Create project with owner A
    project = Project(
        title=TEST_PROJECT_TITLE,
        owner_id=auth_headers['X-User-ID']
    )
    db_session.add(project)
    db_session.commit()

    # Create headers for user B
    other_user_headers = auth_headers.copy()
    other_user_headers['X-User-ID'] = '123456789012345678902'  # Different user ID

    # Test update with non-owner
    update_data = {
        'title': f"{TEST_PROJECT_TITLE}_unauthorized"
    }
    response = test_client.put(
        f"{PROJECTS_URL}/{project.project_id}",
        json=update_data,
        headers=other_user_headers
    )
    
    assert response.status_code == HTTP_STATUS_CODES['FORBIDDEN']
    error_data = response.get_json()
    assert 'error' in error_data
    assert error_data['error']['message'] == ERROR_MESSAGES['PROJECT_ACCESS_DENIED']

    # Verify project unchanged
    db_session.refresh(project)
    assert project.title == TEST_PROJECT_TITLE