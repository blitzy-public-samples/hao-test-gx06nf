"""
Cache configuration module for Redis caching with master-replica support.

This module provides comprehensive Redis cache configuration including:
- Connection parameters and pooling
- TTL settings for different resource types
- Cache key pattern generation
- Master-replica configuration
- Health monitoring and reliability features

Version: 1.0
"""

import os
from typing import Dict, Optional, Any, Final
from config.settings import get_config
from utils.constants import CACHE_CONSTANTS

# Cache type configuration
CACHE_TYPE: Final[str] = 'redis'

# Enhanced Redis configuration with reliability features
CACHE_REDIS_CONFIG: Final[Dict[str, Any]] = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'db': int(os.getenv('REDIS_DB', 0)),
    'password': os.getenv('REDIS_PASSWORD', None),
    'socket_timeout': int(os.getenv('REDIS_SOCKET_TIMEOUT', 5)),
    'socket_connect_timeout': int(os.getenv('REDIS_CONNECT_TIMEOUT', 5)),
    'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', 100)),
    'retry_on_timeout': bool(os.getenv('REDIS_RETRY_ON_TIMEOUT', True)),
    'health_check_interval': int(os.getenv('REDIS_HEALTH_CHECK_INTERVAL', 30)),
    'connection_pool': {
        'max_connections': int(os.getenv('REDIS_POOL_MAX_CONNECTIONS', 100)),
        'timeout': int(os.getenv('REDIS_POOL_TIMEOUT', 20))
    },
    'replica_config': {
        'enabled': bool(os.getenv('REDIS_REPLICA_ENABLED', True)),
        'read_from_replicas': bool(os.getenv('REDIS_READ_REPLICAS', True)),
        'replica_hosts': os.getenv('REDIS_REPLICA_HOSTS', '').split(',')
    }
}

# Cache TTL configuration (in seconds)
CACHE_TTL: Final[Dict[str, int]] = {
    'project_list': CACHE_CONSTANTS['PROJECT_CACHE_TTL'],      # 300s (5 min)
    'specifications': CACHE_CONSTANTS['SPECIFICATION_CACHE_TTL'], # 120s (2 min)
    'items': CACHE_CONSTANTS['ITEMS_CACHE_TTL'],               # 120s (2 min)
    'user_data': CACHE_CONSTANTS['USER_CACHE_TTL']            # 900s (15 min)
}

def get_cache_key_pattern(resource_type: str, resource_id: Optional[str] = None, 
                         version: Optional[str] = None) -> str:
    """
    Generate a cache key pattern for different resource types with optional versioning.

    Args:
        resource_type (str): Type of resource (project_list, specifications, items, user_data)
        resource_id (Optional[str]): Specific resource identifier
        version (Optional[str]): Cache version for invalidation control

    Returns:
        str: Formatted cache key pattern

    Raises:
        ValueError: If resource_type is invalid
    """
    if resource_type not in CACHE_TTL:
        raise ValueError(f"Invalid resource type: {resource_type}")

    # Base key pattern with prefix from constants
    key_pattern = f"{CACHE_CONSTANTS['CACHE_KEY_PREFIX']}:{resource_type}"
    
    # Append resource ID if provided
    if resource_id:
        key_pattern = f"{key_pattern}:{resource_id}"
    
    # Add version suffix if specified
    if version:
        key_pattern = f"{key_pattern}:v{version}"
    
    return key_pattern

class CacheConfig:
    """Enhanced cache configuration class with reliability features and master-replica support."""
    
    def __init__(self) -> None:
        """Initialize cache configuration with environment-specific settings."""
        config = get_config()
        
        self.CACHE_TYPE = CACHE_TYPE
        self.CACHE_REDIS_CONFIG = CACHE_REDIS_CONFIG.copy()
        self.CACHE_TTL = CACHE_TTL.copy()
        
        # Initialize replica configuration
        self._replica_enabled = self.CACHE_REDIS_CONFIG['replica_config']['enabled']
        self._replica_hosts = self.CACHE_REDIS_CONFIG['replica_config']['replica_hosts']
        
        # Validate configuration
        self.validate_config()

    def get_ttl(self, resource_type: str) -> int:
        """
        Get TTL for specific resource type with fallback to default.

        Args:
            resource_type (str): Type of resource

        Returns:
            int: TTL in seconds

        Raises:
            ValueError: If resource_type is invalid
        """
        if resource_type not in self.CACHE_TTL:
            raise ValueError(f"Invalid resource type: {resource_type}")
        
        ttl = self.CACHE_TTL[resource_type]
        
        # Ensure TTL is within reasonable bounds
        if ttl < 60:  # Minimum 1 minute
            ttl = 60
        elif ttl > 86400:  # Maximum 24 hours
            ttl = 86400
            
        return ttl

    def validate_config(self) -> bool:
        """
        Validate Redis configuration parameters.

        Returns:
            bool: True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate required parameters
        required_params = ['host', 'port', 'db']
        missing_params = [param for param in required_params 
                         if not self.CACHE_REDIS_CONFIG.get(param)]
        if missing_params:
            raise ValueError(f"Missing required Redis parameters: {missing_params}")

        # Validate connection settings
        if self.CACHE_REDIS_CONFIG['socket_timeout'] < 1:
            raise ValueError("Socket timeout must be at least 1 second")
        
        if self.CACHE_REDIS_CONFIG['max_connections'] < 1:
            raise ValueError("Max connections must be at least 1")

        # Validate replica configuration if enabled
        if self._replica_enabled and not self._replica_hosts:
            raise ValueError("Replica hosts must be specified when replica mode is enabled")

        # Validate TTL values
        if any(ttl < 0 for ttl in self.CACHE_TTL.values()):
            raise ValueError("Cache TTL values must be positive")

        return True

    def get_connection_pool(self) -> Dict[str, Any]:
        """
        Get Redis connection pool configuration.

        Returns:
            Dict[str, Any]: Connection pool settings
        """
        pool_config = self.CACHE_REDIS_CONFIG['connection_pool'].copy()
        
        # Apply environment-specific overrides
        if os.getenv('FLASK_ENV') == 'production':
            pool_config.update({
                'max_connections': int(os.getenv('REDIS_POOL_MAX_CONNECTIONS', 200)),
                'timeout': int(os.getenv('REDIS_POOL_TIMEOUT', 30))
            })
        
        return pool_config