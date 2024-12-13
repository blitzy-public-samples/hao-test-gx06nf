"""
Integration tests for item management functionality within specifications.
Tests cover item creation, retrieval, ordering, and deletion with emphasis
on data consistency and hierarchy maintenance.

Version: 1.0.0
"""

import pytest
import json
from typing import Dict, Any

from db.models.items import Item
from utils.constants import (
    DATABASE_CONSTANTS,
    ERROR_MESSAGES,
    HTTP_STATUS_CODES
)

@pytest.mark.integration
def test_create_item(test_client, db_session, auth_headers):
    """
    Tests item creation within a specification, validating response codes,
    data persistence, and order index assignment.
    """
    # Create test specification first
    spec_data = {
        "title": "Test Specification",
        "content": "Test Content"
    }
    spec_response = test_client.post(
        "/api/v1/specifications",
        headers=auth_headers,
        json=spec_data
    )
    assert spec_response.status_code == HTTP_STATUS_CODES['CREATED']
    spec_id = json.loads(spec_response.data)['data']['spec_id']

    # Test item creation
    item_data = {
        "content": "Test Item Content",
        "order_index": 0
    }
    response = test_client.post(
        f"/api/v1/specifications/{spec_id}/items",
        headers=auth_headers,
        json=item_data
    )

    # Validate response
    assert response.status_code == HTTP_STATUS_CODES['CREATED']
    response_data = json.loads(response.data)
    assert 'data' in response_data
    assert 'item_id' in response_data['data']
    assert response_data['data']['content'] == item_data['content']
    assert response_data['data']['order_index'] == item_data['order_index']

    # Verify database persistence
    item = db_session.query(Item).filter_by(
        spec_id=spec_id,
        order_index=item_data['order_index']
    ).first()
    assert item is not None
    assert item.content == item_data['content']

@pytest.mark.integration
def test_get_items(test_client, db_session, auth_headers):
    """
    Tests retrieval of items for a specification, verifying ordering,
    pagination, and data consistency.
    """
    # Create test specification
    spec_data = {
        "title": "Test Specification",
        "content": "Test Content"
    }
    spec_response = test_client.post(
        "/api/v1/specifications",
        headers=auth_headers,
        json=spec_data
    )
    spec_id = json.loads(spec_response.data)['data']['spec_id']

    # Create multiple test items
    items_data = [
        {"content": f"Test Item {i}", "order_index": i}
        for i in range(3)
    ]
    for item_data in items_data:
        test_client.post(
            f"/api/v1/specifications/{spec_id}/items",
            headers=auth_headers,
            json=item_data
        )

    # Test items retrieval
    response = test_client.get(
        f"/api/v1/specifications/{spec_id}/items",
        headers=auth_headers
    )

    # Validate response
    assert response.status_code == HTTP_STATUS_CODES['OK']
    response_data = json.loads(response.data)
    assert 'data' in response_data
    assert 'items' in response_data['data']
    assert len(response_data['data']['items']) == 3

    # Verify order
    items = response_data['data']['items']
    for i, item in enumerate(items):
        assert item['order_index'] == i
        assert item['content'] == f"Test Item {i}"

@pytest.mark.integration
def test_update_item_order(test_client, db_session, auth_headers):
    """
    Tests reordering of items within a specification, ensuring order
    consistency and proper index updates.
    """
    # Create test specification
    spec_data = {
        "title": "Test Specification",
        "content": "Test Content"
    }
    spec_response = test_client.post(
        "/api/v1/specifications",
        headers=auth_headers,
        json=spec_data
    )
    spec_id = json.loads(spec_response.data)['data']['spec_id']

    # Create test items
    items_data = [
        {"content": f"Test Item {i}", "order_index": i}
        for i in range(3)
    ]
    created_items = []
    for item_data in items_data:
        response = test_client.post(
            f"/api/v1/specifications/{spec_id}/items",
            headers=auth_headers,
            json=item_data
        )
        created_items.append(json.loads(response.data)['data'])

    # Test reordering - move last item to first position
    item_id = created_items[-1]['item_id']
    new_order = {
        "order_index": 0
    }
    response = test_client.put(
        f"/api/v1/specifications/{spec_id}/items/{item_id}/order",
        headers=auth_headers,
        json=new_order
    )

    # Validate response
    assert response.status_code == HTTP_STATUS_CODES['OK']
    
    # Verify updated order in database
    items = db_session.query(Item).filter_by(spec_id=spec_id).order_by(Item.order_index).all()
    assert items[0].item_id == item_id
    assert items[0].order_index == 0
    for i, item in enumerate(items):
        assert item.order_index == i

@pytest.mark.integration
def test_delete_item(test_client, db_session, auth_headers):
    """
    Tests deletion of an item from a specification, verifying removal
    and order reindexing.
    """
    # Create test specification
    spec_data = {
        "title": "Test Specification",
        "content": "Test Content"
    }
    spec_response = test_client.post(
        "/api/v1/specifications",
        headers=auth_headers,
        json=spec_data
    )
    spec_id = json.loads(spec_response.data)['data']['spec_id']

    # Create test items
    items_data = [
        {"content": f"Test Item {i}", "order_index": i}
        for i in range(3)
    ]
    created_items = []
    for item_data in items_data:
        response = test_client.post(
            f"/api/v1/specifications/{spec_id}/items",
            headers=auth_headers,
            json=item_data
        )
        created_items.append(json.loads(response.data)['data'])

    # Delete middle item
    item_id = created_items[1]['item_id']
    response = test_client.delete(
        f"/api/v1/specifications/{spec_id}/items/{item_id}",
        headers=auth_headers
    )

    # Validate response
    assert response.status_code == HTTP_STATUS_CODES['NO_CONTENT']

    # Verify item removal and order reindexing
    items = db_session.query(Item).filter_by(spec_id=spec_id).order_by(Item.order_index).all()
    assert len(items) == 2
    for i, item in enumerate(items):
        assert item.order_index == i

@pytest.mark.integration
def test_item_limit(test_client, db_session, auth_headers):
    """
    Tests enforcement of the 10-item limit per specification,
    validating error handling.
    """
    # Create test specification
    spec_data = {
        "title": "Test Specification",
        "content": "Test Content"
    }
    spec_response = test_client.post(
        "/api/v1/specifications",
        headers=auth_headers,
        json=spec_data
    )
    spec_id = json.loads(spec_response.data)['data']['spec_id']

    # Create maximum allowed items
    for i in range(DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']):
        item_data = {
            "content": f"Test Item {i}",
            "order_index": i
        }
        response = test_client.post(
            f"/api/v1/specifications/{spec_id}/items",
            headers=auth_headers,
            json=item_data
        )
        assert response.status_code == HTTP_STATUS_CODES['CREATED']

    # Attempt to create one more item
    item_data = {
        "content": "Excess Item",
        "order_index": DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']
    }
    response = test_client.post(
        f"/api/v1/specifications/{spec_id}/items",
        headers=auth_headers,
        json=item_data
    )

    # Validate error response
    assert response.status_code == HTTP_STATUS_CODES['BAD_REQUEST']
    response_data = json.loads(response.data)
    assert 'error' in response_data
    assert response_data['error']['message'] == ERROR_MESSAGES['MAX_ITEMS_REACHED']

    # Verify database still has exactly max items
    item_count = db_session.query(Item).filter_by(spec_id=spec_id).count()
    assert item_count == DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']