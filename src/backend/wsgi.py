"""
WSGI entry point file that creates and exposes the Flask application instance for production deployment.
Implements robust error handling, environment validation, and monitoring support.

Version: 1.0.0
"""

import os
import logging
import sys
from typing import Optional

from src.main import create_app

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger('wsgi')

# Valid deployment environments
VALID_ENVIRONMENTS = ['production', 'staging', 'development']

def validate_environment(env: Optional[str]) -> str:
    """
    Validates the provided environment value against allowed environments.

    Args:
        env: Environment name to validate

    Returns:
        str: Validated environment name, defaults to 'production' if invalid

    Raises:
        ValueError: If environment validation fails
    """
    if not env or env not in VALID_ENVIRONMENTS:
        logger.warning(
            f"Invalid environment specified: {env}. Defaulting to 'production'",
            extra={'environment': env}
        )
        return 'production'
    return env

def init_logging() -> None:
    """
    Initializes logging configuration for the WSGI application.
    Configures log levels, handlers and formats based on environment.
    """
    # Get environment-specific log level
    env = os.getenv('FLASK_ENV', 'production')
    log_level = logging.DEBUG if env == 'development' else logging.INFO
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Add handler if none exists
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
        root_logger.addHandler(handler)
    
    logger.info(
        "Logging initialized",
        extra={
            'environment': env,
            'log_level': logging.getLevelName(log_level)
        }
    )

# Initialize logging
init_logging()

try:
    # Validate environment and create Flask app
    env = validate_environment(os.getenv('FLASK_ENV', 'production'))
    app = create_app(env)
    
    logger.info(
        "WSGI application initialized successfully",
        extra={
            'environment': env,
            'debug': app.debug,
            'testing': app.testing
        }
    )

except Exception as e:
    logger.critical(
        "Failed to initialize WSGI application",
        extra={'error': str(e)},
        exc_info=True
    )
    raise

# Export WSGI application
application = app.wsgi_app