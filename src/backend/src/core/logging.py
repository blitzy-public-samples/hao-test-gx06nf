"""
Core logging module for the Specification Management API.

This module provides comprehensive request logging, context management, and logging utilities with:
- Thread-safe request tracking with unique IDs
- High-precision performance timing
- Structured logging with cloud integration
- Environment-specific configuration
- Request context correlation
- Sanitized logging output

Version: 1.0
"""

import logging  # version: 3.8+
import uuid  # version: 3.8+
import time  # version: 3.8+
from typing import Optional, Dict, Type, Any  # version: 3.8+
from contextvars import ContextVar  # version: 3.8+
from flask import request, has_request_context  # version: 2.0+

from config.logging import setup_logging, get_log_level

# Thread-safe request ID context
request_id_var: ContextVar[str] = ContextVar('request_id', default=None)

# Module logger
logger = logging.getLogger(__name__)

def get_request_id() -> str:
    """
    Get or generate a unique request ID with thread safety.
    
    Returns:
        str: Current request ID or new UUID4 string
    """
    try:
        request_id = request_id_var.get()
        if not request_id:
            request_id = str(uuid.uuid4())
            request_id_var.set(request_id)
        return request_id
    except Exception as e:
        logger.warning(f"Error getting request ID: {e}")
        return str(uuid.uuid4())

def set_request_id(request_id: str) -> None:
    """
    Set request ID in the current context with thread safety.
    
    Args:
        request_id (str): Request ID to set
    """
    try:
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("Invalid request ID format")
        request_id_var.set(request_id)
        logger.debug(f"Set request ID: {request_id}")
    except Exception as e:
        logger.error(f"Failed to set request ID: {e}")

def init_logging() -> None:
    """
    Initialize application logging with environment-specific configuration.
    
    Configures:
    - Environment-specific log levels
    - Request context tracking
    - Performance monitoring
    - Cloud integration (if enabled)
    - Log rotation and buffering
    - Error handling
    """
    try:
        # Initialize base logging configuration
        setup_logging()
        
        # Set root logger level
        root_logger = logging.getLogger()
        root_logger.setLevel(get_log_level())
        
        # Add request context filter to all handlers
        context_filter = RequestContextFilter()
        for handler in root_logger.handlers:
            handler.addFilter(context_filter)
        
        logger.info("Logging system initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize logging: {e}")
        raise

class RequestLogger:
    """
    Thread-safe context manager for request logging with performance tracking.
    
    Provides:
    - Microsecond precision timing
    - Request context correlation
    - Structured logging output
    - Error tracking
    - Performance metrics
    """
    
    def __init__(self, method: str, path: str, headers: Dict[str, str]):
        """
        Initialize request logging context.
        
        Args:
            method (str): HTTP method
            path (str): Request path
            headers (Dict[str, str]): Request headers
        """
        self._method = self._sanitize_string(method)
        self._path = self._sanitize_string(path)
        self._headers = self._sanitize_headers(headers)
        self._start_time: Optional[float] = None
        
        # Initialize request context
        self._request_id = get_request_id()
    
    def __enter__(self) -> 'RequestLogger':
        """
        Enter logging context with precise timing.
        
        Returns:
            RequestLogger: Self reference for context management
        """
        self._start_time = time.perf_counter()
        
        # Log request start
        logger.info(
            f"Request started",
            extra={
                'method': self._method,
                'path': self._path,
                'request_id': self._request_id,
                'duration_ms': 0.0
            }
        )
        return self
    
    def __exit__(self, exc_type: Optional[Type[BaseException]], 
                 exc_value: Optional[BaseException], 
                 traceback: Any) -> None:
        """
        Exit logging context with timing and error handling.
        
        Args:
            exc_type: Exception type if error occurred
            exc_value: Exception instance if error occurred
            traceback: Exception traceback if error occurred
        """
        # Calculate request duration
        duration_ms = 0.0
        if self._start_time is not None:
            duration_ms = (time.perf_counter() - self._start_time) * 1000
        
        # Prepare log context
        log_context = {
            'method': self._method,
            'path': self._path,
            'request_id': self._request_id,
            'duration_ms': duration_ms
        }
        
        # Handle any errors
        if exc_type is not None:
            logger.error(
                f"Request failed: {exc_value}",
                extra={
                    **log_context,
                    'error_type': exc_type.__name__,
                    'error_message': str(exc_value)
                },
                exc_info=(exc_type, exc_value, traceback)
            )
        else:
            logger.info(
                "Request completed",
                extra=log_context
            )
    
    @staticmethod
    def _sanitize_string(value: str) -> str:
        """Sanitize string values for logging."""
        return str(value)[:1000] if value else ''
    
    @staticmethod
    def _sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """
        Sanitize request headers for logging.
        
        Removes sensitive information and limits header values.
        """
        sensitive_headers = {'authorization', 'cookie', 'x-api-key'}
        return {
            k.lower(): '***' if k.lower() in sensitive_headers else v[:200]
            for k, v in headers.items()
        }

class RequestContextFilter(logging.Filter):
    """
    Thread-safe logging filter that adds request context to log records.
    
    Adds:
    - Request ID
    - Performance metrics
    - Environment information
    """
    
    def __init__(self):
        """Initialize the filter with thread safety."""
        super().__init__()
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add request context to log record.
        
        Args:
            record (logging.LogRecord): Log record to enhance
        
        Returns:
            bool: Always True to include record
        """
        # Add request ID
        record.request_id = get_request_id()
        
        # Add request context if available
        if has_request_context():
            record.method = request.method
            record.path = request.path
        else:
            record.method = 'N/A'
            record.path = 'N/A'
        
        # Ensure duration_ms is available
        if not hasattr(record, 'duration_ms'):
            record.duration_ms = 0.0
        
        return True

# Initialize logging on module import
init_logging()

__all__ = [
    'RequestLogger',
    'get_request_id',
    'set_request_id',
    'init_logging'
]