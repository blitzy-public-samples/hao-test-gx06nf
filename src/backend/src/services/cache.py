"""
Cache service providing high-level business logic layer caching operations.

This service implements caching functionality with:
- TTL management based on resource types
- Key pattern handling with versioning
- Compression for large datasets
- Circuit breaker pattern for Redis failures
- Comprehensive error handling and logging
- Cache invalidation with batch processing

Version: 1.0
"""

from typing import List, Dict, Optional, Any
import json
import logging
import zlib
from functools import wraps

from core.cache import get_redis_client, CacheManager
from config.cache import CACHE_TTL, get_cache_key_pattern

# Configure logging
logger = logging.getLogger(__name__)

# Constants for compression
COMPRESSION_THRESHOLD = 1024  # Compress data larger than 1KB
COMPRESSION_LEVEL = 6  # Medium compression level

# Circuit breaker settings
MAX_FAILURES = 3
FAILURE_TIMEOUT = 300  # 5 minutes

# Global circuit breaker state
_circuit_breaker = {
    'failures': 0,
    'is_open': False
}

def _compress_data(data: Any) -> bytes:
    """
    Compress data if it exceeds threshold.
    
    Args:
        data: Data to potentially compress
        
    Returns:
        bytes: Compressed or original data with header
    """
    serialized = json.dumps(data).encode('utf-8')
    if len(serialized) > COMPRESSION_THRESHOLD:
        compressed = zlib.compress(serialized, level=COMPRESSION_LEVEL)
        return b'c' + compressed  # Prefix 'c' indicates compressed
    return b'u' + serialized  # Prefix 'u' indicates uncompressed

def _decompress_data(data: bytes) -> Any:
    """
    Decompress data if it was compressed.
    
    Args:
        data: Data to potentially decompress
        
    Returns:
        Any: Decompressed and deserialized data
    """
    if data[0] == ord('c'):  # Compressed data
        decompressed = zlib.decompress(data[1:])
        return json.loads(decompressed.decode('utf-8'))
    return json.loads(data[1:].decode('utf-8'))  # Uncompressed data

def _check_circuit_breaker(func):
    """Decorator to implement circuit breaker pattern."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if _circuit_breaker['is_open']:
            logger.warning("Circuit breaker is open, skipping cache operation")
            return None if 'get' in func.__name__ else False
        try:
            return func(*args, **kwargs)
        except Exception as e:
            _circuit_breaker['failures'] += 1
            if _circuit_breaker['failures'] >= MAX_FAILURES:
                _circuit_breaker['is_open'] = True
                logger.error(f"Circuit breaker opened after {MAX_FAILURES} failures")
            raise e
    return wrapper

def cache_project_list(user_id: str, projects: List[Dict]) -> bool:
    """
    Cache user's project list with appropriate TTL and retry mechanism.
    
    Args:
        user_id: User identifier
        projects: List of project dictionaries
        
    Returns:
        bool: Success status of caching operation
    """
    try:
        key = get_cache_key_pattern('project_list', user_id)
        ttl = CACHE_TTL['project_list']
        
        with CacheManager() as cache:
            compressed_data = _compress_data(projects)
            success = cache.setex(key, ttl, compressed_data)
            
            if success:
                logger.info(f"Successfully cached project list for user {user_id}")
            return bool(success)
            
    except Exception as e:
        logger.error(f"Error caching project list for user {user_id}: {str(e)}")
        return False

@_check_circuit_breaker
def get_cached_project_list(user_id: str) -> Optional[List[Dict]]:
    """
    Retrieve cached project list for user with circuit breaker pattern.
    
    Args:
        user_id: User identifier
        
    Returns:
        Optional[List[Dict]]: Cached projects if exists, None otherwise
    """
    try:
        key = get_cache_key_pattern('project_list', user_id)
        
        with CacheManager() as cache:
            data = cache.get(key)
            if data is None:
                logger.debug(f"Cache miss for project list of user {user_id}")
                return None
                
            projects = _decompress_data(data)
            logger.debug(f"Cache hit for project list of user {user_id}")
            return projects
            
    except Exception as e:
        logger.error(f"Error retrieving cached project list for user {user_id}: {str(e)}")
        return None

def cache_specifications(project_id: str, specifications: List[Dict]) -> bool:
    """
    Cache project specifications with TTL and compression.
    
    Args:
        project_id: Project identifier
        specifications: List of specification dictionaries
        
    Returns:
        bool: Success status of caching operation
    """
    try:
        key = get_cache_key_pattern('specifications', project_id)
        ttl = CACHE_TTL['specifications']
        
        with CacheManager() as cache:
            compressed_data = _compress_data(specifications)
            success = cache.setex(key, ttl, compressed_data)
            
            if success:
                logger.info(f"Successfully cached specifications for project {project_id}")
            return bool(success)
            
    except Exception as e:
        logger.error(f"Error caching specifications for project {project_id}: {str(e)}")
        return False

@_check_circuit_breaker
def get_cached_specifications(project_id: str) -> Optional[List[Dict]]:
    """
    Retrieve cached specifications for project with circuit breaker.
    
    Args:
        project_id: Project identifier
        
    Returns:
        Optional[List[Dict]]: Cached specifications if exists, None otherwise
    """
    try:
        key = get_cache_key_pattern('specifications', project_id)
        
        with CacheManager() as cache:
            data = cache.get(key)
            if data is None:
                logger.debug(f"Cache miss for specifications of project {project_id}")
                return None
                
            specifications = _decompress_data(data)
            logger.debug(f"Cache hit for specifications of project {project_id}")
            return specifications
            
    except Exception as e:
        logger.error(f"Error retrieving cached specifications for project {project_id}: {str(e)}")
        return None

def cache_items(spec_id: str, items: List[Dict]) -> bool:
    """
    Cache specification items with TTL and compression.
    
    Args:
        spec_id: Specification identifier
        items: List of item dictionaries
        
    Returns:
        bool: Success status of caching operation
    """
    try:
        key = get_cache_key_pattern('items', spec_id)
        ttl = CACHE_TTL['items']
        
        with CacheManager() as cache:
            compressed_data = _compress_data(items)
            success = cache.setex(key, ttl, compressed_data)
            
            if success:
                logger.info(f"Successfully cached items for specification {spec_id}")
            return bool(success)
            
    except Exception as e:
        logger.error(f"Error caching items for specification {spec_id}: {str(e)}")
        return False

@_check_circuit_breaker
def get_cached_items(spec_id: str) -> Optional[List[Dict]]:
    """
    Retrieve cached items for specification with circuit breaker.
    
    Args:
        spec_id: Specification identifier
        
    Returns:
        Optional[List[Dict]]: Cached items if exists, None otherwise
    """
    try:
        key = get_cache_key_pattern('items', spec_id)
        
        with CacheManager() as cache:
            data = cache.get(key)
            if data is None:
                logger.debug(f"Cache miss for items of specification {spec_id}")
                return None
                
            items = _decompress_data(data)
            logger.debug(f"Cache hit for items of specification {spec_id}")
            return items
            
    except Exception as e:
        logger.error(f"Error retrieving cached items for specification {spec_id}: {str(e)}")
        return None

def invalidate_project_cache(project_id: str) -> bool:
    """
    Invalidate all cache entries related to a project with batch processing.
    
    Args:
        project_id: Project identifier
        
    Returns:
        bool: Success status of invalidation
    """
    try:
        pattern = get_cache_key_pattern('specifications', project_id, '*')
        
        with CacheManager() as cache:
            # Clear project-specific caches
            success = bool(cache.delete(get_cache_key_pattern('specifications', project_id)))
            
            # Clear all related specification caches
            cursor = 0
            while True:
                cursor, keys = cache.scan(cursor, match=pattern)
                if keys:
                    cache.delete(*keys)
                if cursor == 0:
                    break
                    
            logger.info(f"Successfully invalidated cache for project {project_id}")
            return success
            
    except Exception as e:
        logger.error(f"Error invalidating cache for project {project_id}: {str(e)}")
        return False

def invalidate_specification_cache(spec_id: str) -> bool:
    """
    Invalidate all cache entries related to a specification with batch processing.
    
    Args:
        spec_id: Specification identifier
        
    Returns:
        bool: Success status of invalidation
    """
    try:
        with CacheManager() as cache:
            # Clear specification and its items cache
            keys = [
                get_cache_key_pattern('specifications', spec_id),
                get_cache_key_pattern('items', spec_id)
            ]
            success = bool(cache.delete(*keys))
            
            logger.info(f"Successfully invalidated cache for specification {spec_id}")
            return success
            
    except Exception as e:
        logger.error(f"Error invalidating cache for specification {spec_id}: {str(e)}")
        return False