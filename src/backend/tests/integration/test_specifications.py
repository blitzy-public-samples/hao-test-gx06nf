"""
Integration tests for the Specification Management API endpoints.

This module implements comprehensive integration tests for specification-related operations including:
- CRUD operations with database validation
- Authentication and authorization checks
- Performance monitoring and validation
- Data integrity verification
- Error handling validation

Version: 1.0
"""

import pytest
import json
import time
from typing import Dict, Any, List
from datetime import datetime

from utils.constants import (
    DATABASE_CONSTANTS,
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    API_CONSTANTS
)

# API endpoint constants
BASE_URL = '/api/v1/specifications'
TEST_PROJECT_ID = 1
RESPONSE_TIME_THRESHOLD = 500  # milliseconds

@pytest.mark.integration
class TestSpecificationsAPI:
    """Integration test suite for specifications API endpoints."""

    def __init__(self):
        """Initialize test class with test data."""
        self.test_data: Dict[str, Any] = {
            'specification': {
                'content': 'Test Specification',
                'project_id': TEST_PROJECT_ID,
                'order_index': 1
            },
            'items': [
                {'content': f'Test Item {i}', 'order_index': i}
                for i in range(3)
            ]
        }
        self.start_time: float = 0.0

    def setup_method(self, method):
        """
        Setup method for each test with database preparation and performance monitoring.

        Args:
            method: Test method being executed
        """
        # Record start time for performance measurement
        self.start_time = time.time()

        # Clear any existing test data
        self.teardown_method(method)

    def teardown_method(self, method):
        """
        Cleanup method after each test.

        Args:
            method: Test method being executed
        """
        # Log performance metrics
        execution_time = (time.time() - self.start_time) * 1000
        print(f"\nTest {method.__name__} execution time: {execution_time:.2f}ms")

    @pytest.mark.integration
    def test_get_project_specifications_authenticated(
        self,
        test_client,
        auth_headers,
        db_session
    ):
        """
        Test retrieving specifications list for a project with valid authentication.

        Args:
            test_client: Flask test client fixture
            auth_headers: Authentication headers fixture
            db_session: Database session fixture
        """
        # Record start time for performance measurement
        start_time = time.time()

        # Create test specifications
        for i in range(3):
            spec_data = {
                'content': f'Test Specification {i}',
                'project_id': TEST_PROJECT_ID,
                'order_index': i
            }
            response = test_client.post(
                BASE_URL,
                headers=auth_headers,
                json=spec_data
            )
            assert response.status_code == HTTP_STATUS_CODES['CREATED']

        # Get specifications list
        response = test_client.get(
            f"{BASE_URL}/project/{TEST_PROJECT_ID}",
            headers=auth_headers
        )

        # Validate response
        assert response.status_code == HTTP_STATUS_CODES['OK']
        data = json.loads(response.data)
        
        # Validate response structure
        assert 'data' in data
        assert 'items' in data['data']
        assert 'metadata' in data['data']
        
        # Validate specifications order
        specs = data['data']['items']
        assert len(specs) == 3
        for i in range(len(specs) - 1):
            assert specs[i]['order_index'] < specs[i + 1]['order_index']

        # Validate pagination metadata
        assert data['data']['metadata']['total'] == 3
        assert data['data']['metadata']['page'] == 1

        # Validate performance
        execution_time = (time.time() - start_time) * 1000
        assert execution_time < RESPONSE_TIME_THRESHOLD

    @pytest.mark.integration
    def test_get_project_specifications_unauthorized(self, test_client):
        """
        Test unauthorized access to specifications.

        Args:
            test_client: Flask test client fixture
        """
        # Test without authentication
        response = test_client.get(f"{BASE_URL}/project/{TEST_PROJECT_ID}")
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']
        
        # Test with invalid token
        response = test_client.get(
            f"{BASE_URL}/project/{TEST_PROJECT_ID}",
            headers={'Authorization': 'Bearer invalid_token'}
        )
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']

        # Validate error response format
        data = json.loads(response.data)
        assert 'error' in data
        assert 'message' in data['error']
        assert data['error']['message'] == ERROR_MESSAGES['INVALID_TOKEN']

    @pytest.mark.integration
    def test_create_specification(
        self,
        test_client,
        auth_headers,
        db_session
    ):
        """
        Test specification creation with validation.

        Args:
            test_client: Flask test client fixture
            auth_headers: Authentication headers fixture
            db_session: Database session fixture
        """
        start_time = time.time()

        # Create specification
        response = test_client.post(
            BASE_URL,
            headers=auth_headers,
            json=self.test_data['specification']
        )

        # Validate response
        assert response.status_code == HTTP_STATUS_CODES['CREATED']
        data = json.loads(response.data)
        
        # Validate created specification
        assert 'data' in data
        spec = data['data']
        assert spec['content'] == self.test_data['specification']['content']
        assert spec['project_id'] == TEST_PROJECT_ID
        assert spec['order_index'] == 1
        assert 'created_at' in spec

        # Validate performance
        execution_time = (time.time() - start_time) * 1000
        assert execution_time < RESPONSE_TIME_THRESHOLD

        # Test validation errors
        invalid_data = {
            'content': 'x' * (DATABASE_CONSTANTS['MAX_CONTENT_LENGTH'] + 1),
            'project_id': TEST_PROJECT_ID,
            'order_index': -1
        }
        response = test_client.post(
            BASE_URL,
            headers=auth_headers,
            json=invalid_data
        )
        assert response.status_code == HTTP_STATUS_CODES['BAD_REQUEST']

    @pytest.mark.integration
    def test_update_specification_order(
        self,
        test_client,
        auth_headers,
        db_session
    ):
        """
        Test updating specification order with concurrent update handling.

        Args:
            test_client: Flask test client fixture
            auth_headers: Authentication headers fixture
            db_session: Database session fixture
        """
        start_time = time.time()

        # Create test specifications
        spec_ids = []
        for i in range(3):
            response = test_client.post(
                BASE_URL,
                headers=auth_headers,
                json={
                    'content': f'Test Specification {i}',
                    'project_id': TEST_PROJECT_ID,
                    'order_index': i
                }
            )
            data = json.loads(response.data)
            spec_ids.append(data['data']['id'])

        # Update order
        new_order = {
            'specifications': [
                {'id': spec_ids[0], 'order_index': 2},
                {'id': spec_ids[1], 'order_index': 0},
                {'id': spec_ids[2], 'order_index': 1}
            ]
        }
        response = test_client.put(
            f"{BASE_URL}/order",
            headers=auth_headers,
            json=new_order
        )

        # Validate response
        assert response.status_code == HTTP_STATUS_CODES['OK']
        
        # Verify new order
        response = test_client.get(
            f"{BASE_URL}/project/{TEST_PROJECT_ID}",
            headers=auth_headers
        )
        data = json.loads(response.data)
        specs = data['data']['items']
        
        assert specs[0]['id'] == spec_ids[1]
        assert specs[1]['id'] == spec_ids[2]
        assert specs[2]['id'] == spec_ids[0]

        # Validate performance
        execution_time = (time.time() - start_time) * 1000
        assert execution_time < RESPONSE_TIME_THRESHOLD

    @pytest.mark.integration
    def test_delete_specification(
        self,
        test_client,
        auth_headers,
        db_session
    ):
        """
        Test specification deletion with cascade and authorization checks.

        Args:
            test_client: Flask test client fixture
            auth_headers: Authentication headers fixture
            db_session: Database session fixture
        """
        start_time = time.time()

        # Create test specification
        response = test_client.post(
            BASE_URL,
            headers=auth_headers,
            json=self.test_data['specification']
        )
        spec_id = json.loads(response.data)['data']['id']

        # Add items to specification
        for item in self.test_data['items']:
            response = test_client.post(
                f"{BASE_URL}/{spec_id}/items",
                headers=auth_headers,
                json=item
            )
            assert response.status_code == HTTP_STATUS_CODES['CREATED']

        # Delete specification
        response = test_client.delete(
            f"{BASE_URL}/{spec_id}",
            headers=auth_headers
        )
        assert response.status_code == HTTP_STATUS_CODES['NO_CONTENT']

        # Verify deletion
        response = test_client.get(
            f"{BASE_URL}/{spec_id}",
            headers=auth_headers
        )
        assert response.status_code == HTTP_STATUS_CODES['NOT_FOUND']

        # Verify items are deleted
        response = test_client.get(
            f"{BASE_URL}/{spec_id}/items",
            headers=auth_headers
        )
        assert response.status_code == HTTP_STATUS_CODES['NOT_FOUND']

        # Validate performance
        execution_time = (time.time() - start_time) * 1000
        assert execution_time < RESPONSE_TIME_THRESHOLD

        # Test unauthorized deletion
        response = test_client.delete(
            f"{BASE_URL}/{spec_id}",
            headers={'Authorization': 'Bearer invalid_token'}
        )
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']