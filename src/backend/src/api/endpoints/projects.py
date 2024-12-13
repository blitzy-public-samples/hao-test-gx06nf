"""
REST API endpoint implementations for project management with comprehensive security,
caching, rate limiting and error handling.

This module implements the following endpoints:
- GET /projects - List user's projects with caching
- POST /projects - Create new project with validation
- PUT /projects/{id} - Update project with ownership verification
- DELETE /projects/{id} - Delete project with cleanup

Version: 1.0
"""

import logging
from datetime import datetime
from typing import Dict, Any

from flask import Blueprint, jsonify, request, g
from http import HTTPStatus

from ...services.projects import ProjectService
from ..schemas.projects import ProjectCreate, ProjectResponse
from ..auth.decorators import require_auth, require_project_owner
from flask_caching import cache  # version: 1.10+
from flask_limiter import rate_limit  # version: 1.0+

from ...utils.constants import (
    HTTP_STATUS_CODES,
    ERROR_MESSAGES,
    CACHE_CONSTANTS,
    RATE_LIMIT_CONSTANTS
)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize blueprint
projects_router = Blueprint('projects', __name__)

@projects_router.route('/', methods=['GET'])
@require_auth
@rate_limit(limit=RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR'], period=3600)
@cache.cached(
    timeout=CACHE_CONSTANTS['PROJECT_CACHE_TTL'],
    key_prefix=lambda: f'projects_list_{g.user_id}'
)
async def get_projects():
    """
    Get all projects owned by authenticated user with caching and rate limiting.

    Returns:
        Response: JSON list of user's projects with metadata
        
    Raises:
        HTTPError: If request is invalid or unauthorized
    """
    try:
        logger.debug(f"Fetching projects for user {g.user_id}")
        
        # Get projects from service
        project_service = ProjectService()
        projects = await project_service.get_user_projects(g.user_id)
        
        # Convert to response schema
        project_responses = [
            ProjectResponse.from_orm(project).dict() 
            for project in projects
        ]
        
        # Return formatted response
        return jsonify({
            'status': 'success',
            'data': {
                'items': project_responses,
                'metadata': {
                    'total': len(project_responses),
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
        }), HTTP_STATUS_CODES['OK']
        
    except ValueError as e:
        logger.error(f"Validation error in get_projects: {str(e)}")
        return jsonify({
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']
        
    except Exception as e:
        logger.error(f"Error fetching projects: {str(e)}")
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@projects_router.route('/', methods=['POST'])
@require_auth
@rate_limit(limit=100, period=3600)
async def create_project():
    """
    Create new project for authenticated user with validation.

    Returns:
        Response: JSON of created project with metadata
        
    Raises:
        HTTPError: If request is invalid or unauthorized
    """
    try:
        logger.debug(f"Creating project for user {g.user_id}")
        
        # Validate request data
        project_data = ProjectCreate(**request.get_json())
        
        # Create project
        project_service = ProjectService()
        created_project = await project_service.create_project(
            g.user_id,
            project_data
        )
        
        # Convert to response schema
        project_response = ProjectResponse.from_orm(created_project).dict()
        
        # Invalidate projects list cache
        cache.delete(f'projects_list_{g.user_id}')
        
        # Return success response
        return jsonify({
            'status': 'success',
            'data': {
                'project': project_response,
                'metadata': {
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
        }), HTTP_STATUS_CODES['CREATED']
        
    except ValueError as e:
        logger.error(f"Validation error in create_project: {str(e)}")
        return jsonify({
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']
        
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@projects_router.route('/<int:project_id>', methods=['PUT'])
@require_auth
@require_project_owner
@rate_limit(limit=100, period=3600)
async def update_project(project_id: int):
    """
    Update project if user is owner with validation.

    Args:
        project_id: ID of project to update

    Returns:
        Response: JSON of updated project with metadata
        
    Raises:
        HTTPError: If request is invalid or unauthorized
    """
    try:
        logger.debug(f"Updating project {project_id} for user {g.user_id}")
        
        # Validate request data
        project_data = ProjectCreate(**request.get_json())
        
        # Update project
        project_service = ProjectService()
        updated_project = await project_service.update_project(
            g.user_id,
            project_id,
            project_data
        )
        
        if not updated_project:
            return jsonify({
                'error': {
                    'code': 'NOT_FOUND',
                    'message': ERROR_MESSAGES['RESOURCE_NOT_FOUND'],
                    'timestamp': datetime.utcnow().isoformat()
                }
            }), HTTP_STATUS_CODES['NOT_FOUND']
        
        # Convert to response schema
        project_response = ProjectResponse.from_orm(updated_project).dict()
        
        # Invalidate caches
        cache.delete(f'projects_list_{g.user_id}')
        cache.delete(f'project_{project_id}')
        
        # Return success response
        return jsonify({
            'status': 'success',
            'data': {
                'project': project_response,
                'metadata': {
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
        }), HTTP_STATUS_CODES['OK']
        
    except ValueError as e:
        logger.error(f"Validation error in update_project: {str(e)}")
        return jsonify({
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['BAD_REQUEST']
        
    except Exception as e:
        logger.error(f"Error updating project: {str(e)}")
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']

@projects_router.route('/<int:project_id>', methods=['DELETE'])
@require_auth
@require_project_owner
@rate_limit(limit=50, period=3600)
async def delete_project(project_id: int):
    """
    Delete project if user is owner with cleanup.

    Args:
        project_id: ID of project to delete

    Returns:
        Response: Empty response with 204 status
        
    Raises:
        HTTPError: If request is invalid or unauthorized
    """
    try:
        logger.debug(f"Deleting project {project_id} for user {g.user_id}")
        
        # Delete project
        project_service = ProjectService()
        success = await project_service.delete_project(g.user_id, project_id)
        
        if not success:
            return jsonify({
                'error': {
                    'code': 'NOT_FOUND',
                    'message': ERROR_MESSAGES['RESOURCE_NOT_FOUND'],
                    'timestamp': datetime.utcnow().isoformat()
                }
            }), HTTP_STATUS_CODES['NOT_FOUND']
        
        # Invalidate caches
        cache.delete(f'projects_list_{g.user_id}')
        cache.delete(f'project_{project_id}')
        
        # Return success response
        return '', HTTP_STATUS_CODES['NO_CONTENT']
        
    except Exception as e:
        logger.error(f"Error deleting project: {str(e)}")
        return jsonify({
            'error': {
                'code': 'SERVER_ERROR',
                'message': 'An unexpected error occurred',
                'timestamp': datetime.utcnow().isoformat()
            }
        }), HTTP_STATUS_CODES['SERVER_ERROR']