"""
Alembic migrations environment configuration for the Specification Management API.
Configures database migration environment with Cloud SQL support, connection pooling,
and comprehensive error handling.

Version: 1.0.0
"""

import logging
import os
from logging.config import fileConfig
from time import sleep
from typing import Optional

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from db.base import Base  # SQLAlchemy models metadata
from config.database import DatabaseConfig  # Database configuration

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('alembic.env')

# Alembic Config object
config = context.config

# Interpret the config file for Python logging if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy MetaData object containing all model definitions
target_metadata = Base.metadata

# Constants for retry logic
RETRY_COUNT: int = 3
RETRY_DELAY: int = 5

def get_url() -> str:
    """
    Constructs database URL with proper Cloud SQL and SSL configuration.
    
    Returns:
        str: Configured database URL
    """
    url = DatabaseConfig.SQLALCHEMY_DATABASE_URI
    
    # Add SSL configuration for production if available
    if os.getenv('FLASK_ENV') == 'production' and DatabaseConfig.SSL_CA:
        url = f"{url}?sslmode=verify-full&sslcert={DatabaseConfig.SSL_CA}"
    
    return url

def run_migrations_offline() -> None:
    """
    Runs migrations in 'offline' mode for generating SQL scripts.
    
    This function configures the migration context for script generation
    without requiring a database connection.
    """
    try:
        url = get_url()
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
            compare_server_default=True
        )

        with context.begin_transaction():
            context.run_migrations()
            logger.info("Offline migrations completed successfully")

    except Exception as e:
        logger.error(f"Error during offline migrations: {str(e)}")
        raise

def run_migrations_online() -> None:
    """
    Runs migrations in 'online' mode with direct database connection.
    
    Implements connection pooling, retry logic, and comprehensive error handling
    for robust migration execution.
    """
    # Configure SQLAlchemy engine with production-ready settings
    config_section = config.get_section(config.config_ini_section)
    if config_section is None:
        config_section = {}
    
    config_section['sqlalchemy.url'] = get_url()
    
    # Set up connection pooling
    config_section['sqlalchemy.pool_size'] = DatabaseConfig.POOL_SIZE
    config_section['sqlalchemy.pool_timeout'] = DatabaseConfig.POOL_TIMEOUT
    config_section['sqlalchemy.pool_recycle'] = DatabaseConfig.POOL_RECYCLE
    config_section['sqlalchemy.max_overflow'] = 5

    # Initialize retry counter
    retry_count: int = RETRY_COUNT

    while retry_count > 0:
        try:
            connectable = engine_from_config(
                config_section,
                prefix='sqlalchemy.',
                poolclass=pool.QueuePool,
                connect_args={
                    'connect_timeout': 60,
                    'options': '-c statement_timeout=60000'
                }
            )

            with connectable.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    compare_type=True,
                    compare_server_default=True,
                    # Enable transaction per migration
                    transaction_per_migration=True,
                    # Configure lock timeout
                    dialect_opts={
                        "paramstyle": "named",
                        "lock_timeout": "10000"
                    }
                )

                with context.begin_transaction():
                    context.run_migrations()
                    logger.info("Online migrations completed successfully")
                return

        except OperationalError as e:
            retry_count -= 1
            if retry_count == 0:
                logger.error(f"Failed to connect to database after {RETRY_COUNT} attempts: {str(e)}")
                raise
            logger.warning(f"Database connection failed, retrying in {RETRY_DELAY} seconds...")
            sleep(RETRY_DELAY)

        except SQLAlchemyError as e:
            logger.error(f"Database error during migration: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error during migration: {str(e)}")
            raise

        finally:
            if 'connectable' in locals():
                connectable.dispose()

if context.is_offline_mode():
    logger.info("Running migrations in offline mode")
    run_migrations_offline()
else:
    logger.info("Running migrations in online mode")
    run_migrations_online()