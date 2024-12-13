"""
Flask REST API endpoint implementation for managing second-level items within specifications.
Provides CRUD operations and ordering capabilities with comprehensive security, validation,
and performance optimizations through caching and connection pooling.

Version: 1.0.0
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from flask import Blueprint, jsonify, request, g
from flask_caching import cache  # version: 1.10+

from ...services.items import ItemService
from ..schemas.items import ItemCreate, ItemUpdate
from ..auth.decorators import require_auth
from ...utils.constants import (
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    DATABASE_CONSTANTS,
    CACHE_CONSTANTS
)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize blueprint
items_bp = Blueprint('items', __name__, url_prefix='/api/v1/items')

# Cache configuration
CACHE_TIMEOUT = CACHE_CONSTANTS['ITEMS_CACHE_TTL']
MAX_ITEMS_PER_SPEC = DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']

@items_bp.route('/<int:spec_id>', methods=['GET'])
@require_auth
@cache.cached(timeout=CACHE_TIMEOUT)
async def get_specification_items(spec_id: int):
    """
    Retrieve all items for a specific specification with caching.

    Args:
        spec_id (int): ID of the specification to get items for

    Returns:
        Response: JSON list of items with metadata
    """
    try:
        # Initialize service
        item_service = ItemService()
        
        # Get items with ordering
        items = await item_service.get_items_by_specification(spec_id)
        
        # Prepare response
        response = {
            'data': {
                'items': items,
                'metadata': {
                    'total': len(items),
                    'spec_id': spec_id
                }
            },
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(
            "Retrieved items for specification",
            extra={
                'spec_id': spec_id,
                'item_count': len(items),
                'user_id': g.user_id
            }
        )
        
        return jsonify(response), HTTP_STATUS_CODES['OK']

    except ValueError as e:
        logger.error(
            "Invalid specification ID",
            extra={
                'spec_id': spec_id,
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'INVALID_INPUT',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    except Exception as e:
        logger.error(
            "Error retrieving items",
            extra={
                'spec_id': spec_id,
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@items_bp.route('/', methods=['POST'])
@require_auth
async def create_item():
    """
    Create a new item within a specification with validation.

    Returns:
        Response: JSON of created item with metadata
    """
    try:
        # Validate request data
        data = request.get_json()
        item_data = ItemCreate(**data)
        
        # Initialize service
        item_service = ItemService()
        
        # Create item
        created_item = await item_service.create_item(item_data)
        
        # Invalidate cache for specification
        cache.delete_memoized(get_specification_items, item_data.spec_id)
        
        # Prepare response
        response = {
            'data': {
                'item': created_item,
                'metadata': {
                    'spec_id': item_data.spec_id
                }
            },
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(
            "Created new item",
            extra={
                'spec_id': item_data.spec_id,
                'item_id': created_item['item_id'],
                'user_id': g.user_id
            }
        )
        
        return jsonify(response), HTTP_STATUS_CODES['CREATED']

    except ValueError as e:
        logger.error(
            "Invalid item data",
            extra={
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'INVALID_INPUT',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    except Exception as e:
        logger.error(
            "Error creating item",
            extra={
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@items_bp.route('/<int:item_id>', methods=['PUT'])
@require_auth
async def update_item(item_id: int):
    """
    Update an existing item's content or order with validation.

    Args:
        item_id (int): ID of the item to update

    Returns:
        Response: JSON of updated item with metadata
    """
    try:
        # Validate request data
        data = request.get_json()
        item_data = ItemUpdate(**data)
        
        # Initialize service
        item_service = ItemService()
        
        # Update item
        updated_item = await item_service.update_item(item_id, item_data)
        
        # Invalidate cache for specification
        cache.delete_memoized(get_specification_items, updated_item['spec_id'])
        
        # Prepare response
        response = {
            'data': {
                'item': updated_item,
                'metadata': {
                    'spec_id': updated_item['spec_id']
                }
            },
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(
            "Updated item",
            extra={
                'item_id': item_id,
                'user_id': g.user_id
            }
        )
        
        return jsonify(response), HTTP_STATUS_CODES['OK']

    except ValueError as e:
        logger.error(
            "Invalid update data",
            extra={
                'item_id': item_id,
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'INVALID_INPUT',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    except Exception as e:
        logger.error(
            "Error updating item",
            extra={
                'item_id': item_id,
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@items_bp.route('/<int:item_id>', methods=['DELETE'])
@require_auth
async def delete_item(item_id: int):
    """
    Delete an item and reorder remaining items with transaction.

    Args:
        item_id (int): ID of the item to delete

    Returns:
        Response: Empty response with 204 status
    """
    try:
        # Initialize service
        item_service = ItemService()
        
        # Delete item and get specification ID
        spec_id = await item_service.delete_item(item_id)
        
        # Invalidate cache for specification
        cache.delete_memoized(get_specification_items, spec_id)
        
        logger.info(
            "Deleted item",
            extra={
                'item_id': item_id,
                'spec_id': spec_id,
                'user_id': g.user_id
            }
        )
        
        return '', HTTP_STATUS_CODES['NO_CONTENT']

    except ValueError as e:
        logger.error(
            "Invalid item deletion",
            extra={
                'item_id': item_id,
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'INVALID_INPUT',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    except Exception as e:
        logger.error(
            "Error deleting item",
            extra={
                'item_id': item_id,
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@items_bp.route('/<int:spec_id>/reorder', methods=['PUT'])
@require_auth
async def reorder_items(spec_id: int):
    """
    Update the order of multiple items within a specification atomically.

    Args:
        spec_id (int): ID of the specification containing items to reorder

    Returns:
        Response: JSON list of reordered items with metadata
    """
    try:
        # Validate request data
        data = request.get_json()
        if not isinstance(data, list):
            raise ValueError("Invalid reorder data format")
        
        # Initialize service
        item_service = ItemService()
        
        # Reorder items
        reordered_items = await item_service.reorder_items(spec_id, data)
        
        # Invalidate cache for specification
        cache.delete_memoized(get_specification_items, spec_id)
        
        # Prepare response
        response = {
            'data': {
                'items': reordered_items,
                'metadata': {
                    'spec_id': spec_id,
                    'total': len(reordered_items)
                }
            },
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(
            "Reordered items",
            extra={
                'spec_id': spec_id,
                'item_count': len(reordered_items),
                'user_id': g.user_id
            }
        )
        
        return jsonify(response), HTTP_STATUS_CODES['OK']

    except ValueError as e:
        logger.error(
            "Invalid reorder data",
            extra={
                'spec_id': spec_id,
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'INVALID_INPUT',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    except Exception as e:
        logger.error(
            "Error reordering items",
            extra={
                'spec_id': spec_id,
                'error': str(e),
                'user_id': g.user_id
            }
        )
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']