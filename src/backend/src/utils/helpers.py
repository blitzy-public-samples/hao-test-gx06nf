"""
Helper functions module providing common utilities for the specification management system.

This module contains utility functions for:
- API response formatting
- Order index calculations
- Timestamp formatting
- JSON parsing
- Cache key generation

Version: 1.0
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import json
import logging
from utils.constants import (
    DATABASE_CONSTANTS,
    CACHE_CONSTANTS,
)

# Configure logging
logger = logging.getLogger(__name__)

def format_response(
    data: Any,
    status: str = "success",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Formats API response according to standard structure.

    Args:
        data: Response payload data
        status: Response status ("success" or "error")
        metadata: Optional metadata dictionary

    Returns:
        Dict containing formatted response with data, status, metadata, and timestamp

    Example:
        >>> format_response({"items": []}, "success", {"total": 0})
        {
            "data": {"items": []},
            "status": "success",
            "metadata": {"total": 0},
            "timestamp": "2024-01-20T12:00:00Z"
        }
    """
    if status not in ["success", "error"]:
        logger.warning(f"Invalid status value: {status}, defaulting to 'error'")
        status = "error"

    response = {
        "data": data,
        "status": status,
        "timestamp": format_timestamp(datetime.utcnow())
    }

    if metadata is not None:
        if not isinstance(metadata, dict):
            logger.warning("Invalid metadata type, must be dictionary")
        else:
            response["metadata"] = metadata

    return response

def calculate_order_index(
    existing_indices: List[int],
    target_position: Optional[int] = None
) -> int:
    """
    Calculates new order index for specifications or items.

    Args:
        existing_indices: List of existing order indices
        target_position: Optional target position in the list (0-based)

    Returns:
        New order index value

    Raises:
        ValueError: If target_position is out of bounds
    """
    # Sort existing indices
    sorted_indices = sorted(existing_indices)
    
    # Handle empty list case
    if not sorted_indices:
        return (DATABASE_CONSTANTS['MAX_ORDER_INDEX'] - 
                DATABASE_CONSTANTS['MIN_ORDER_INDEX']) // 2

    # Validate target position
    if target_position is not None:
        if target_position < 0 or target_position > len(sorted_indices):
            raise ValueError("Target position out of bounds")

    # Calculate spacing
    min_idx = DATABASE_CONSTANTS['MIN_ORDER_INDEX']
    max_idx = DATABASE_CONSTANTS['MAX_ORDER_INDEX']
    
    if target_position is None or target_position >= len(sorted_indices):
        # Append at end
        prev_index = sorted_indices[-1] if sorted_indices else min_idx
        new_index = prev_index + (max_idx - prev_index) // 2
    elif target_position == 0:
        # Insert at beginning
        next_index = sorted_indices[0]
        new_index = min_idx + (next_index - min_idx) // 2
    else:
        # Insert between existing indices
        prev_index = sorted_indices[target_position - 1]
        next_index = sorted_indices[target_position]
        new_index = prev_index + (next_index - prev_index) // 2

    # Check for index overflow
    if new_index <= min_idx or new_index >= max_idx:
        logger.warning("Order index approaching limits, rebalancing recommended")
        if new_index <= min_idx:
            new_index = min_idx + 1
        if new_index >= max_idx:
            new_index = max_idx - 1

    return new_index

def format_timestamp(dt: datetime) -> str:
    """
    Formats datetime object to ISO-8601 string.

    Args:
        dt: Datetime object to format

    Returns:
        ISO-8601 formatted timestamp string

    Example:
        >>> format_timestamp(datetime(2024, 1, 20, 12, 0, 0))
        "2024-01-20T12:00:00Z"
    """
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def safe_json_loads(json_str: str) -> Union[Dict, List, None]:
    """
    Safely loads JSON string with error handling.

    Args:
        json_str: JSON string to parse

    Returns:
        Parsed JSON data or None if invalid

    Example:
        >>> safe_json_loads('{"key": "value"}')
        {"key": "value"}
        >>> safe_json_loads('invalid json')
        None
    """
    if not isinstance(json_str, str):
        logger.error(f"Invalid input type for JSON parsing: {type(json_str)}")
        return None

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {str(e)}")
        return None

def generate_cache_key(resource_type: str, resource_id: str) -> str:
    """
    Generates cache key for different resource types.

    Args:
        resource_type: Type of resource (project, specification, item)
        resource_id: Unique identifier for the resource

    Returns:
        Formatted cache key string

    Example:
        >>> generate_cache_key("project", "123")
        "spec_mgmt:project:123"
    """
    VALID_RESOURCE_TYPES = ['project', 'specification', 'item', 'user']
    
    if resource_type not in VALID_RESOURCE_TYPES:
        logger.error(f"Invalid resource type: {resource_type}")
        raise ValueError(f"Invalid resource type. Must be one of: {VALID_RESOURCE_TYPES}")

    # Sanitize resource_id
    safe_resource_id = str(resource_id).replace(':', '_')
    
    cache_key = f"{CACHE_CONSTANTS['CACHE_KEY_PREFIX']}:{resource_type}:{safe_resource_id}"
    logger.debug(f"Generated cache key: {cache_key}")
    
    return cache_key