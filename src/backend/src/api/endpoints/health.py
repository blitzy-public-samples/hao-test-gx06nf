"""
Health check endpoint implementation for monitoring system component status.

This module provides comprehensive health monitoring capabilities including:
- Database connectivity and connection pool metrics
- Redis cache availability and performance
- System latency measurements
- Component-specific status reporting
- Aggregated health status with detailed metrics

Version: 1.0
"""

import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from flask import Blueprint, jsonify
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError

from core.database import get_engine
from core.cache import get_redis_client

# Configure module logger
logger = logging.getLogger(__name__)

# Create health check blueprint
health_bp = Blueprint('health', __name__, url_prefix='/health')

def check_database() -> Dict[str, Any]:
    """
    Verify database connectivity and collect connection pool metrics.

    Returns:
        Dict[str, Any]: Database health status and metrics
    """
    try:
        engine = get_engine()
        start_time = datetime.utcnow()
        
        # Execute simple query to verify connectivity
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        
        # Calculate query latency
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Collect pool metrics
        pool = engine.pool
        pool_metrics = {
            'total_size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow()
        }
        
        return {
            'status': 'healthy',
            'latency_ms': round(latency, 2),
            'connection_pool': pool_metrics,
            'message': 'Database connection successful'
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'message': 'Database connection failed'
        }

def check_cache() -> Dict[str, Any]:
    """
    Verify Redis cache connectivity and measure performance.

    Returns:
        Dict[str, Any]: Cache health status and metrics
    """
    try:
        redis_client = get_redis_client()
        start_time = datetime.utcnow()
        
        # Verify connectivity with PING
        redis_client.ping()
        
        # Calculate ping latency
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Get Redis info for memory usage
        info = redis_client.info(section='memory')
        memory_metrics = {
            'used_memory': info.get('used_memory_human'),
            'peak_memory': info.get('used_memory_peak_human'),
            'fragmentation_ratio': info.get('mem_fragmentation_ratio')
        }
        
        return {
            'status': 'healthy',
            'latency_ms': round(latency, 2),
            'memory': memory_metrics,
            'message': 'Cache connection successful'
        }
        
    except RedisError as e:
        logger.error(f"Cache health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'message': 'Cache connection failed'
        }

@health_bp.route('/', methods=['GET'])
def health_check() -> Tuple[Dict[str, Any], int]:
    """
    Main health check endpoint aggregating component status and metrics.

    Returns:
        Tuple[Dict[str, Any], int]: Health check response and HTTP status code
    """
    start_time = datetime.utcnow()
    
    # Check component health
    db_health = check_database()
    cache_health = check_cache()
    
    # Calculate overall API latency
    api_latency = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    # Determine overall system health
    components_healthy = (
        db_health['status'] == 'healthy' and 
        cache_health['status'] == 'healthy'
    )
    
    response = {
        'status': 'healthy' if components_healthy else 'degraded',
        'timestamp': datetime.utcnow().isoformat(),
        'api_latency_ms': round(api_latency, 2),
        'components': {
            'database': db_health,
            'cache': cache_health
        }
    }
    
    # Add version info
    response['version'] = {
        'api': 'v1',
        'environment': 'production'  # This should be environment-specific
    }
    
    # Determine HTTP status code
    status_code = 200 if components_healthy else 503
    
    # Log health check results
    logger.info(f"Health check completed. Status: {response['status']}")
    if not components_healthy:
        logger.warning("System health degraded. Check component status.")
    
    return jsonify(response), status_code