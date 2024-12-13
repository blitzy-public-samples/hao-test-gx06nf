"""
Initialization module for Alembic database migrations that configures migration settings,
logging, and imports required dependencies for database schema management with enhanced
monitoring and connection pool integration.

This module provides:
- Comprehensive migration logging setup
- Connection pool configuration
- Migration environment initialization
- Error handling and monitoring

Version: 1.0.0
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

import alembic
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from db.base import Base
from db.session import engine, SessionLocal
from config.settings import get_config

# Configure logging
logger = logging.getLogger('alembic.migrations')

# Constants for logging configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = 'migrations.log'
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

def configure_logging() -> None:
    """
    Configures comprehensive logging for migration operations with file and console output.
    Includes rotation policies and detailed formatting.
    """
    logger.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)

    # Configure file handler with rotation
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Configure SQLAlchemy pool logging
    logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)
    
    logger.info("Migration logging configured successfully")

def init_alembic() -> None:
    """
    Initializes Alembic migration environment with proper configuration.
    Sets up version locations, templates, and transaction handling.
    """
    try:
        # Get configuration based on environment
        config = get_config()
        
        # Create Alembic configuration
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "migrations")
        alembic_cfg.set_main_option("sqlalchemy.url", config.SQLALCHEMY_DATABASE_URI)
        
        # Configure connection pool settings from engine
        alembic_cfg.attributes['connection'] = engine.connect()
        
        # Set up version locations
        migrations_dir = os.path.join(os.path.dirname(__file__), 'versions')
        if not os.path.exists(migrations_dir):
            os.makedirs(migrations_dir)
            logger.info(f"Created migrations directory: {migrations_dir}")
        
        # Initialize migration context
        context = MigrationContext.configure(
            connection=engine.connect(),
            opts={
                'compare_type': True,
                'compare_server_default': True,
                'target_metadata': Base.metadata,
                'include_schemas': True
            }
        )
        
        # Set up script directory
        script = ScriptDirectory.from_config(alembic_cfg)
        
        # Configure template parameters
        alembic_cfg.set_main_option('file_template', '%%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s')
        
        logger.info("Alembic environment initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Alembic environment: {str(e)}")
        raise
    finally:
        # Ensure connection is closed
        if 'connection' in alembic_cfg.attributes:
            alembic_cfg.attributes['connection'].close()

# Configure logging on module import
configure_logging()

# Export configured objects
__all__ = ['logger', 'init_alembic']