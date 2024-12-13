"""
Comprehensive unit test suite for service layer implementations covering authentication,
project management, and specification management with complete mocking and validation.

Version: 1.0
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from typing import Dict, Any

from services.auth import AuthenticationService
from services.projects import ProjectService
from services.specifications import SpecificationService
from api.schemas.projects import ProjectCreate, ProjectResponse
from utils.constants import (
    ERROR_MESSAGES,
    HTTP_STATUS_CODES,
    DATABASE_CONSTANTS
)

# Test data constants
MOCK_GOOGLE_TOKEN = "mock_google_token"
MOCK_GOOGLE_ID = "123456789012345678901"
MOCK_EMAIL = "test@example.com"
MOCK_PROJECT_ID = 1
MOCK_SPEC_ID = 1

@pytest.mark.asyncio
class TestAuthenticationService:
    """Test suite for authentication service covering Google OAuth flow and session management."""

    @pytest.fixture
    def auth_service(self):
        """Fixture providing configured authentication service with mocked dependencies."""
        service = AuthenticationService()
        service._google_client = MagicMock()
        service._jwt_handler = MagicMock()
        service._user_repository = MagicMock()
        return service

    async def test_authenticate_google_user_success(self, auth_service):
        """Test successful Google OAuth authentication flow with token generation."""
        # Setup mock responses
        auth_service._google_client.verify_oauth_token.return_value = {
            'sub': MOCK_GOOGLE_ID,
            'email': MOCK_EMAIL
        }
        auth_service._jwt_handler.generate_token.return_value = "mock_jwt_token"
        auth_service._user_repository.get_by_google_id.return_value = None
        auth_service._user_repository.create_google_user.return_value = MagicMock(
            google_id=MOCK_GOOGLE_ID,
            email=MOCK_EMAIL
        )

        # Execute test
        result = await auth_service.authenticate_google_user(
            MOCK_GOOGLE_TOKEN,
            "mock_fingerprint"
        )

        # Verify results
        assert result['token'] == "mock_jwt_token"
        assert result['user']['google_id'] == MOCK_GOOGLE_ID
        auth_service._google_client.verify_oauth_token.assert_called_once_with(MOCK_GOOGLE_TOKEN)
        auth_service._user_repository.create_google_user.assert_called_once()

    async def test_validate_session_success(self, auth_service):
        """Test successful JWT session validation with cache integration."""
        # Setup mock responses
        mock_payload = {
            'sub': MOCK_GOOGLE_ID,
            'email': MOCK_EMAIL,
            'fingerprint': "mock_fingerprint"
        }
        auth_service._jwt_handler.validate_token.return_value = mock_payload
        auth_service._jwt_handler.is_blacklisted.return_value = False
        auth_service._user_repository.get_by_google_id.return_value = MagicMock(
            google_id=MOCK_GOOGLE_ID,
            email=MOCK_EMAIL
        )

        # Execute test
        result = await auth_service.validate_session(
            "Bearer mock_jwt_token",
            "mock_fingerprint"
        )

        # Verify results
        assert result['session_valid'] is True
        assert result['user']['google_id'] == MOCK_GOOGLE_ID
        auth_service._jwt_handler.validate_token.assert_called_once()
        auth_service._user_repository.get_by_google_id.assert_called_once_with(MOCK_GOOGLE_ID)

@pytest.mark.asyncio
class TestProjectService:
    """Test suite for project service covering CRUD operations and caching."""

    @pytest.fixture
    def project_service(self):
        """Fixture providing configured project service with mocked dependencies."""
        repository = MagicMock()
        return ProjectService(repository)

    async def test_get_user_projects_success(self, project_service):
        """Test successful project listing with cache integration."""
        # Setup mock data
        mock_projects = [
            MagicMock(
                project_id=1,
                title="Test Project 1",
                owner_id=MOCK_GOOGLE_ID,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            ),
            MagicMock(
                project_id=2,
                title="Test Project 2",
                owner_id=MOCK_GOOGLE_ID,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
        ]
        project_service._repository.get_by_owner.return_value = mock_projects

        # Execute test
        result = await project_service.get_user_projects(MOCK_GOOGLE_ID)

        # Verify results
        assert len(result) == 2
        assert result[0].project_id == 1
        assert result[1].project_id == 2
        project_service._repository.get_by_owner.assert_called_once_with(MOCK_GOOGLE_ID)

    async def test_create_project_success(self, project_service):
        """Test successful project creation with validation."""
        # Setup mock data
        project_data = ProjectCreate(title="New Project")
        mock_project = MagicMock(
            project_id=1,
            title="New Project",
            owner_id=MOCK_GOOGLE_ID,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        project_service._repository.create_project.return_value = mock_project
        project_service._repository.get_by_owner.return_value = []

        # Execute test
        result = await project_service.create_project(MOCK_GOOGLE_ID, project_data)

        # Verify results
        assert isinstance(result, ProjectResponse)
        assert result.title == "New Project"
        assert result.owner_id == MOCK_GOOGLE_ID
        project_service._repository.create_project.assert_called_once()

@pytest.mark.asyncio
class TestSpecificationService:
    """Test suite for specification service covering hierarchical operations."""

    @pytest.fixture
    def spec_service(self):
        """Fixture providing configured specification service with mocked dependencies."""
        return SpecificationService()

    async def test_get_project_specifications_success(self, spec_service):
        """Test successful specification listing with ordering."""
        # Setup mock data
        mock_specs = [
            MagicMock(
                spec_id=1,
                project_id=MOCK_PROJECT_ID,
                content="Spec 1",
                order_index=0
            ),
            MagicMock(
                spec_id=2,
                project_id=MOCK_PROJECT_ID,
                content="Spec 2",
                order_index=1
            )
        ]
        spec_service._repository.get_by_project.return_value = mock_specs

        # Execute test
        result = await spec_service.get_project_specifications(
            MOCK_PROJECT_ID,
            MOCK_GOOGLE_ID
        )

        # Verify results
        assert len(result) == 2
        assert result[0].spec_id == 1
        assert result[1].spec_id == 2
        spec_service._repository.get_by_project.assert_called_once_with(
            project_id=MOCK_PROJECT_ID,
            owner_id=MOCK_GOOGLE_ID
        )

    async def test_create_specification_success(self, spec_service):
        """Test successful specification creation with validation."""
        # Setup mock data
        mock_spec = MagicMock(
            spec_id=MOCK_SPEC_ID,
            project_id=MOCK_PROJECT_ID,
            content="New Specification",
            order_index=0
        )
        spec_service._repository.create_specification.return_value = mock_spec

        # Execute test
        result = await spec_service.create_specification(
            MOCK_PROJECT_ID,
            "New Specification",
            MOCK_GOOGLE_ID
        )

        # Verify results
        assert result.spec_id == MOCK_SPEC_ID
        assert result.content == "New Specification"
        spec_service._repository.create_specification.assert_called_once_with(
            project_id=MOCK_PROJECT_ID,
            content="New Specification",
            owner_id=MOCK_GOOGLE_ID
        )