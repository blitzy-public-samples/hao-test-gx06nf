"""
REST API endpoint implementation for managing specifications within projects.
Provides CRUD operations with enhanced caching, security, and performance optimizations.

Version: 1.0.0
"""

import logging
from typing import Dict, Any
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, g
from prometheus_client import Counter, Histogram

from ...services.specifications import SpecificationService
from ...services.cache import (
    get_cached_specifications,
    cache_specifications,
    invalidate_specification_cache
)
from ..auth.decorators import require_auth
from ...utils.constants import (
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    DATABASE_CONSTANTS
)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Blueprint
specifications_bp = Blueprint('specifications', __name__, url_prefix='/api/v1/specifications')

# Initialize services
specification_service = SpecificationService()

# Prometheus metrics
SPECIFICATION_REQUESTS = Counter(
    'specification_requests_total',
    'Total specification endpoint requests',
    ['method', 'endpoint']
)
SPECIFICATION_LATENCY = Histogram(
    'specification_request_duration_seconds',
    'Specification endpoint request duration',
    ['method', 'endpoint']
)
CACHE_HITS = Counter(
    'specification_cache_hits_total',
    'Number of specification cache hits'
)
CACHE_MISSES = Counter(
    'specification_cache_misses_total',
    'Number of specification cache misses'
)

@specifications_bp.route('/project/<int:project_id>', methods=['GET'])
@require_auth
def get_project_specifications(project_id: int):
    """
    Retrieve all specifications for a project with caching and monitoring.

    Args:
        project_id (int): Project identifier

    Returns:
        Response: JSON list of specifications with metadata
    """
    try:
        SPECIFICATION_REQUESTS.labels(
            method='GET',
            endpoint='/project/<id>'
        ).inc()

        start_time = datetime.now(timezone.utc)

        # Check cache first
        cached_specs = get_cached_specifications(str(project_id))
        if cached_specs is not None:
            CACHE_HITS.inc()
            logger.debug(f"Cache hit for project specifications: {project_id}")
            
            return jsonify({
                'data': cached_specs,
                'metadata': {
                    'cached': True,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            }), HTTP_STATUS_CODES['OK']

        CACHE_MISSES.inc()

        # Get specifications from service
        specifications = specification_service.get_project_specifications(
            project_id=project_id,
            owner_id=g.user_id
        )

        # Cache the results
        cache_specifications(str(project_id), specifications)

        # Record latency
        SPECIFICATION_LATENCY.labels(
            method='GET',
            endpoint='/project/<id>'
        ).observe(
            (datetime.now(timezone.utc) - start_time).total_seconds()
        )

        return jsonify({
            'data': specifications,
            'metadata': {
                'cached': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['OK']

    except ValueError as e:
        logger.warning(
            f"Invalid request for project specifications: {str(e)}",
            extra={'project_id': project_id}
        )
        return jsonify({
            'error': {
                'code': 'INVALID_REQUEST',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    except Exception as e:
        logger.error(
            f"Error retrieving project specifications: {str(e)}",
            extra={'project_id': project_id},
            exc_info=True
        )
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@specifications_bp.route('', methods=['POST'])
@require_auth
def create_specification():
    """
    Create a new specification with validation and cache invalidation.

    Returns:
        Response: JSON of created specification
    """
    try:
        SPECIFICATION_REQUESTS.labels(
            method='POST',
            endpoint=''
        ).inc()

        start_time = datetime.now(timezone.utc)

        # Validate request data
        data = request.get_json()
        if not data or 'project_id' not in data or 'content' not in data:
            raise ValueError("Missing required fields: project_id, content")

        # Validate content length
        if len(data['content']) > DATABASE_CONSTANTS['MAX_CONTENT_LENGTH']:
            raise ValueError(
                f"Content exceeds maximum length of {DATABASE_CONSTANTS['MAX_CONTENT_LENGTH']} characters"
            )

        # Create specification
        specification = specification_service.create_specification(
            project_id=data['project_id'],
            content=data['content'],
            owner_id=g.user_id
        )

        # Invalidate project specifications cache
        invalidate_specification_cache(str(data['project_id']))

        # Record latency
        SPECIFICATION_LATENCY.labels(
            method='POST',
            endpoint=''
        ).observe(
            (datetime.now(timezone.utc) - start_time).total_seconds()
        )

        return jsonify({
            'data': specification,
            'metadata': {
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['CREATED']

    except ValueError as e:
        logger.warning(
            f"Invalid specification creation request: {str(e)}",
            extra={'request_data': data}
        )
        return jsonify({
            'error': {
                'code': 'INVALID_REQUEST',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    except Exception as e:
        logger.error(
            f"Error creating specification: {str(e)}",
            extra={'request_data': data},
            exc_info=True
        )
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@specifications_bp.route('/<int:spec_id>/order', methods=['PUT'])
@require_auth
def update_specification_order(spec_id: int):
    """
    Update specification order with cache refresh.

    Args:
        spec_id (int): Specification identifier

    Returns:
        Response: JSON success response
    """
    try:
        SPECIFICATION_REQUESTS.labels(
            method='PUT',
            endpoint='/<id>/order'
        ).inc()

        start_time = datetime.now(timezone.utc)

        # Validate request data
        data = request.get_json()
        if not data or 'order_index' not in data:
            raise ValueError("Missing required field: order_index")

        # Update order
        success = specification_service.update_specification_order(
            spec_id=spec_id,
            new_order_index=data['order_index'],
            owner_id=g.user_id
        )

        if not success:
            raise ValueError("Failed to update specification order")

        # Record latency
        SPECIFICATION_LATENCY.labels(
            method='PUT',
            endpoint='/<id>/order'
        ).observe(
            (datetime.now(timezone.utc) - start_time).total_seconds()
        )

        return jsonify({
            'data': {'success': True},
            'metadata': {
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['OK']

    except ValueError as e:
        logger.warning(
            f"Invalid specification order update request: {str(e)}",
            extra={'spec_id': spec_id, 'request_data': data}
        )
        return jsonify({
            'error': {
                'code': 'INVALID_REQUEST',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    except Exception as e:
        logger.error(
            f"Error updating specification order: {str(e)}",
            extra={'spec_id': spec_id, 'request_data': data},
            exc_info=True
        )
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@specifications_bp.route('/<int:spec_id>', methods=['DELETE'])
@require_auth
def delete_specification(spec_id: int):
    """
    Delete specification with cache cleanup.

    Args:
        spec_id (int): Specification identifier

    Returns:
        Response: Empty response with 204 status
    """
    try:
        SPECIFICATION_REQUESTS.labels(
            method='DELETE',
            endpoint='/<id>'
        ).inc()

        start_time = datetime.now(timezone.utc)

        # Delete specification
        success = specification_service.delete_specification(
            spec_id=spec_id,
            owner_id=g.user_id
        )

        if not success:
            raise ValueError("Failed to delete specification")

        # Record latency
        SPECIFICATION_LATENCY.labels(
            method='DELETE',
            endpoint='/<id>'
        ).observe(
            (datetime.now(timezone.utc) - start_time).total_seconds()
        )

        return '', HTTP_STATUS_CODES['NO_CONTENT']

    except ValueError as e:
        logger.warning(
            f"Invalid specification deletion request: {str(e)}",
            extra={'spec_id': spec_id}
        )
        return jsonify({
            'error': {
                'code': 'INVALID_REQUEST',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']

    except Exception as e:
        logger.error(
            f"Error deleting specification: {str(e)}",
            extra={'spec_id': spec_id},
            exc_info=True
        )
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']