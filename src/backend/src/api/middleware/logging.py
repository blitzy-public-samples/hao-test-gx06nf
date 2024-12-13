"""
Enhanced logging middleware module for the Specification Management API.

This module provides comprehensive request logging, timing tracking, and request context
management with:
- Request/response logging with sanitization
- Performance monitoring and cloud metrics
- Security context tracking
- Distributed tracing integration
- Cloud logging integration

Version: 1.0
"""

import time
from typing import Any, Callable, Dict, Optional, Union
from functools import wraps
from flask import request, g, Response
from opentelemetry import trace  # version: 1.0+
from google.cloud import logging as cloud_logging  # version: 3.0+

from core.logging import (
    RequestLogger,
    get_request_id,
    set_request_id
)
from core.security import sanitize_log_data

# Initialize tracers and loggers
tracer = trace.get_tracer(__name__)
cloud_logger = cloud_logging.Client().logger('spec-mgmt-api')

# Configuration constants
SAMPLE_RATE: float = 0.1  # Sample 10% of requests for detailed logging
PERFORMANCE_THRESHOLD_MS: int = 500  # Performance threshold from technical specs

class RequestLoggingMiddleware:
    """
    Enhanced WSGI middleware for comprehensive request logging with security monitoring
    and cloud integration.
    """

    def __init__(self, app: Any) -> None:
        """
        Initialize the logging middleware with cloud integration.

        Args:
            app: Flask application instance
        """
        self._app = app
        self._cloud_logger = cloud_logging.Client().logger('spec-mgmt-api')
        self._tracer = trace.get_tracer(__name__)

    def __call__(self, environ: Dict, start_response: Callable) -> Any:
        """
        Process each request with comprehensive logging and monitoring.

        Args:
            environ: WSGI environment dictionary
            start_response: WSGI start_response callable

        Returns:
            Any: WSGI response
        """
        # Generate request ID and create trace context
        request_id = get_request_id()
        set_request_id(request_id)

        # Start trace span
        with self._tracer.start_as_current_span("http_request") as span:
            span.set_attribute("request.id", request_id)
            
            # Create request logger with sanitized data
            request_data = {
                'method': environ.get('REQUEST_METHOD'),
                'path': environ.get('PATH_INFO'),
                'query': environ.get('QUERY_STRING'),
                'remote_addr': environ.get('REMOTE_ADDR'),
                'user_agent': environ.get('HTTP_USER_AGENT')
            }
            sanitized_data = sanitize_log_data(request_data)

            with RequestLogger(
                method=sanitized_data['method'],
                path=sanitized_data['path'],
                headers=environ
            ) as logger:
                # Track request timing
                start_time = time.perf_counter()

                # Process request through application
                def custom_start_response(status: str, headers: list, exc_info: Optional[Any] = None) -> Any:
                    # Log response status
                    logger.add_metric('response_status', status.split()[0])
                    return start_response(status, headers, exc_info)

                try:
                    response = self._app(environ, custom_start_response)
                    
                    # Calculate and log request duration
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    logger.add_metric('duration_ms', duration_ms)

                    # Log performance warning if threshold exceeded
                    if duration_ms > PERFORMANCE_THRESHOLD_MS:
                        self._cloud_logger.warning(
                            f"Request exceeded performance threshold",
                            {
                                'request_id': request_id,
                                'duration_ms': duration_ms,
                                'threshold_ms': PERFORMANCE_THRESHOLD_MS,
                                'path': sanitized_data['path']
                            }
                        )

                    # Send metrics to cloud monitoring
                    self._cloud_logger.log_struct({
                        'request_id': request_id,
                        'method': sanitized_data['method'],
                        'path': sanitized_data['path'],
                        'duration_ms': duration_ms,
                        'status': g.get('response_status', 'unknown')
                    })

                    return response

                except Exception as e:
                    # Log error details
                    logger.add_metric('error', str(e))
                    self._cloud_logger.error(
                        f"Request failed: {str(e)}",
                        {
                            'request_id': request_id,
                            'error_type': type(e).__name__,
                            'path': sanitized_data['path']
                        }
                    )
                    raise

def log_request(f: Callable) -> Callable:
    """
    Enhanced decorator for logging HTTP requests with timing and security context.

    Args:
        f: Function to wrap with logging

    Returns:
        Callable: Wrapped function with comprehensive request logging
    """
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        request_id = get_request_id()
        
        # Sample request for detailed logging
        should_log_details = time.time() % (1/SAMPLE_RATE) < 1
        
        # Create request logger with sanitized data
        sanitized_headers = sanitize_log_data(dict(request.headers))
        
        with RequestLogger(
            method=request.method,
            path=request.path,
            headers=sanitized_headers
        ) as logger:
            # Track request timing
            start_time = time.perf_counter()
            
            try:
                # Execute request handler
                response: Union[Response, tuple] = f(*args, **kwargs)
                
                # Calculate request duration
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.add_metric('duration_ms', duration_ms)
                
                # Log detailed request data if sampled
                if should_log_details:
                    cloud_logger.log_struct({
                        'request_id': request_id,
                        'method': request.method,
                        'path': request.path,
                        'duration_ms': duration_ms,
                        'status_code': response.status_code if isinstance(response, Response) else response[1],
                        'sampled': True
                    })
                
                # Check performance threshold
                if duration_ms > PERFORMANCE_THRESHOLD_MS:
                    cloud_logger.warning(
                        f"Request exceeded performance threshold",
                        {
                            'request_id': request_id,
                            'duration_ms': duration_ms,
                            'threshold_ms': PERFORMANCE_THRESHOLD_MS
                        }
                    )
                
                return response
                
            except Exception as e:
                # Log error details
                logger.add_metric('error', str(e))
                cloud_logger.error(
                    f"Request failed: {str(e)}",
                    {
                        'request_id': request_id,
                        'error_type': type(e).__name__,
                        'path': request.path
                    }
                )
                raise
            
    return wrapper

__all__ = ['RequestLoggingMiddleware', 'log_request']