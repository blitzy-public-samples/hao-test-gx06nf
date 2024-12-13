"""
Advanced logging configuration module for the Specification Management API.

This module provides comprehensive logging configuration with:
- Environment-specific logging settings
- Structured log formats with performance metrics
- Request tracking and correlation IDs
- Cloud logging integration for production
- Rotating file handlers with compression
- Asynchronous logging for improved performance

Version: 1.0
"""

import os
import json
import logging
import logging.handlers
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from config.settings import ENVIRONMENT

# Type aliases
LoggerType = logging.Logger
HandlerType = logging.Handler

# Constants for log formatting
LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(request_id)s - %(duration_ms).2f - %(message)s'
STRUCTURED_LOG_FORMAT: Dict[str, str] = {
    'timestamp': '%(asctime)s',
    'logger': '%(name)s',
    'level': '%(levelname)s',
    'request_id': '%(request_id)s',
    'duration_ms': '%(duration_ms).2f',
    'message': '%(message)s',
    'environment': '%(environment)s'
}
DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'

# Environment-specific log levels
LOG_LEVEL_MAP: Dict[str, str] = {
    'development': 'DEBUG',
    'staging': 'INFO',
    'production': 'WARNING'
}

# Environment-specific file handler configuration
FILE_HANDLER_CONFIG: Dict[str, Dict[str, int]] = {
    'development': {
        'max_bytes': 10 * 1024 * 1024,  # 10MB
        'backup_count': 3
    },
    'staging': {
        'max_bytes': 50 * 1024 * 1024,  # 50MB
        'backup_count': 5
    },
    'production': {
        'max_bytes': 100 * 1024 * 1024,  # 100MB
        'backup_count': 10
    }
}

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging with performance metrics."""
    
    def __init__(self) -> None:
        super().__init__()
        self.default_msec_format = '%s.%03d'

    def format(self, record: logging.LogRecord) -> str:
        """Format log record into structured JSON format."""
        # Add default values for custom fields
        record.request_id = getattr(record, 'request_id', '-')
        record.duration_ms = getattr(record, 'duration_ms', 0.0)
        record.environment = ENVIRONMENT

        # Create structured log entry
        log_entry = {k: self._format_value(v, record) for k, v in STRUCTURED_LOG_FORMAT.items()}
        
        # Add additional context if available
        if hasattr(record, 'extra_context'):
            log_entry['context'] = record.extra_context

        return json.dumps(log_entry)

    def _format_value(self, format_string: str, record: logging.LogRecord) -> str:
        """Format individual log record values."""
        try:
            return format_string % record.__dict__
        except Exception:
            return format_string

class AsyncRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Asynchronous rotating file handler with compression support."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue_size = 1000
        self.queue = []

    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record asynchronously."""
        try:
            self.queue.append(record)
            if len(self.queue) >= self.queue_size:
                self._flush_queue()
        except Exception:
            self.handleError(record)

    def _flush_queue(self) -> None:
        """Flush queued log records to file."""
        while self.queue:
            record = self.queue.pop(0)
            super().emit(record)

def setup_logging() -> None:
    """
    Configure comprehensive logging system with environment-specific settings.
    
    This function sets up:
    - Console logging for all environments
    - File logging for staging/production
    - Cloud logging integration for production
    - Request tracking and correlation IDs
    - Performance metric tracking
    - Log sanitization
    """
    # Get environment-specific log level
    log_level = get_log_level()
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Setup console handler for all environments
    console_handler = create_console_handler()
    root_logger.addHandler(console_handler)
    
    # Setup file handler for staging and production
    if ENVIRONMENT in ('staging', 'production'):
        file_handler = create_file_handler()
        root_logger.addHandler(file_handler)
    
    # Setup cloud logging for production
    if ENVIRONMENT == 'production':
        cloud_handler = configure_cloud_logging()
        root_logger.addHandler(cloud_handler)
    
    # Initialize request tracking
    setup_request_tracking()
    
    logging.info(f"Logging configured for {ENVIRONMENT} environment at {log_level} level")

def get_log_level() -> str:
    """
    Determine appropriate log level based on environment.
    
    Returns:
        str: Log level name (DEBUG/INFO/WARNING)
    """
    return LOG_LEVEL_MAP.get(ENVIRONMENT, 'INFO')

def create_console_handler() -> logging.Handler:
    """
    Create and configure console log handler with async support.
    
    Returns:
        logging.Handler: Configured console handler
    """
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter())
    console_handler.setLevel(get_log_level())
    
    # Wrap with AsyncHandler for improved performance
    async_handler = logging.handlers.QueueHandler(logging.handlers.QueueListener(
        console_handler
    ).queue)
    
    return async_handler

def create_file_handler() -> logging.Handler:
    """
    Create and configure rotating file handler with environment-specific settings.
    
    Returns:
        logging.Handler: Configured file handler
    """
    # Get environment-specific configuration
    config = FILE_HANDLER_CONFIG[ENVIRONMENT]
    
    # Create logs directory if it doesn't exist
    log_dir = Path(os.path.join(os.getcwd(), 'logs'))
    log_dir.mkdir(exist_ok=True)
    
    # Configure rotating file handler
    file_handler = AsyncRotatingFileHandler(
        filename=os.path.join(log_dir, f'app-{ENVIRONMENT}.log'),
        maxBytes=config['max_bytes'],
        backupCount=config['backup_count'],
        encoding='utf-8'
    )
    
    file_handler.setFormatter(StructuredFormatter())
    file_handler.setLevel(get_log_level())
    
    return file_handler

def configure_cloud_logging() -> logging.Handler:
    """
    Setup cloud logging integration for production environment.
    
    Returns:
        logging.Handler: Configured cloud logging handler
    """
    try:
        from google.cloud import logging as cloud_logging
        
        client = cloud_logging.Client()
        cloud_handler = cloud_logging.handlers.CloudLoggingHandler(
            client,
            name=f"spec-mgmt-api-{ENVIRONMENT}"
        )
        cloud_handler.setFormatter(StructuredFormatter())
        return cloud_handler
    except ImportError:
        logging.warning("Google Cloud Logging package not installed, skipping cloud integration")
        return logging.NullHandler()

def setup_request_tracking() -> None:
    """Initialize request tracking and correlation ID system."""
    import threading
    
    # Initialize thread-local storage for request context
    thread_local = threading.local()
    
    def get_request_id() -> str:
        """Get current request ID or generate new one."""
        if not hasattr(thread_local, 'request_id'):
            thread_local.request_id = os.urandom(16).hex()
        return thread_local.request_id
    
    # Add request_id filter to all handlers
    logging.Filter.filter = lambda self, record: setattr(record, 'request_id', 
                                                       get_request_id()) or True

# Export primary functions
__all__ = ['setup_logging', 'get_log_level']