"""
Database configuration module for the Specification Management API.

This module provides comprehensive database configuration including:
- PostgreSQL connection settings
- SQLAlchemy configuration
- Connection pooling parameters
- SSL certificate management
- Google Cloud SQL integration
- Performance optimization settings

Version: 1.0
"""

import os
import ssl
import uuid
from typing import Dict, Any, Optional
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from config.settings import Config, ENV, DEBUG

# Database connection parameters
POSTGRES_SERVER: str = os.getenv('POSTGRES_SERVER', 'localhost')
POSTGRES_USER: str = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD: str = os.getenv('POSTGRES_PASSWORD', '')
POSTGRES_DB: str = os.getenv('POSTGRES_DB', 'app')
POSTGRES_PORT: str = os.getenv('POSTGRES_PORT', '5432')

# SSL certificate paths
SSL_CERT_PATH: str = os.getenv('SSL_CERT_PATH', '')
SSL_KEY_PATH: str = os.getenv('SSL_KEY_PATH', '')
SSL_ROOT_CERT_PATH: str = os.getenv('SSL_ROOT_CERT_PATH', '')

class DatabaseConfig:
    """Database configuration class with comprehensive connection and performance settings."""

    def __init__(self) -> None:
        """Initialize database configuration with environment-specific settings."""
        # Basic SQLAlchemy settings
        self.SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
        self.SQLALCHEMY_ECHO: bool = DEBUG
        self.SQLALCHEMY_ENGINE_ID: str = str(uuid.uuid4())

        # Generate database URI
        self.SQLALCHEMY_DATABASE_URI: str = self.get_database_uri()

        # Configure connection pool settings
        self.SQLALCHEMY_ENGINE_OPTIONS: Dict[str, Any] = {
            # Pool size configuration
            'pool_size': 10,
            'max_overflow': 20,
            'pool_timeout': 30,
            'pool_recycle': 1800,
            
            # Connection verification
            'pool_pre_ping': True,
            
            # Performance settings
            'pool_use_lifo': True,
            'echo_pool': DEBUG,
            
            # Query execution timeouts
            'connect_args': {
                'connect_timeout': 10,
                'application_name': f'spec_mgmt_{ENV}_{self.SQLALCHEMY_ENGINE_ID}',
                'options': '-c statement_timeout=30000'  # 30 second query timeout
            }
        }

        # Configure SSL for production
        if ENV == 'production':
            self._configure_ssl()

    def get_database_uri(self) -> str:
        """
        Construct database URI with appropriate configuration and security settings.

        Returns:
            str: Fully configured PostgreSQL connection URI
        """
        # Check for Google Cloud SQL socket
        cloud_sql_socket = os.getenv('CLOUD_SQL_CONNECTION_NAME')
        if cloud_sql_socket and ENV == 'production':
            return f'postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@/{POSTGRES_DB}' \
                   f'?host=/cloudsql/{cloud_sql_socket}'

        # Construct standard PostgreSQL URI
        base_uri = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}' \
                  f'@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}'

        # Add SSL parameters for production
        if ENV == 'production' and self.validate_ssl_config():
            ssl_params = [
                f'sslmode=verify-full',
                f'sslcert={SSL_CERT_PATH}',
                f'sslkey={SSL_KEY_PATH}',
                f'sslrootcert={SSL_ROOT_CERT_PATH}'
            ]
            base_uri = f'{base_uri}?{"&".join(ssl_params)}'

        return base_uri

    def validate_ssl_config(self) -> bool:
        """
        Validate SSL certificate configuration for production environment.

        Returns:
            bool: True if SSL configuration is valid
        
        Raises:
            ValueError: If SSL configuration is invalid
        """
        if ENV != 'production':
            return False

        required_ssl_files = [
            (SSL_CERT_PATH, 'SSL certificate'),
            (SSL_KEY_PATH, 'SSL key'),
            (SSL_ROOT_CERT_PATH, 'SSL root certificate')
        ]

        for file_path, file_type in required_ssl_files:
            if not file_path:
                raise ValueError(f'Missing {file_type} path in production environment')
            
            path = Path(file_path)
            if not path.exists():
                raise ValueError(f'{file_type} file not found: {file_path}')
            
            if not path.is_file():
                raise ValueError(f'{file_type} path is not a file: {file_path}')

        return True

    def _configure_ssl(self) -> None:
        """Configure SSL context and settings for production environment."""
        if self.validate_ssl_config():
            ssl_context = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH,
                cafile=SSL_ROOT_CERT_PATH
            )
            ssl_context.load_cert_chain(
                certfile=SSL_CERT_PATH,
                keyfile=SSL_KEY_PATH
            )
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            ssl_context.check_hostname = True

            self.SQLALCHEMY_ENGINE_OPTIONS['connect_args']['ssl_context'] = ssl_context

    @staticmethod
    @event.listens_for(Engine, 'connect')
    def _on_connect(dbapi_connection, connection_record) -> None:
        """
        Configure connection-level settings on connect.
        
        Args:
            dbapi_connection: Raw database connection
            connection_record: Connection pool record
        """
        # Set session parameters for performance
        cursor = dbapi_connection.cursor()
        cursor.execute("SET timezone TO 'UTC'")
        cursor.execute("SET application_name TO 'spec_mgmt'")
        cursor.execute("SET statement_timeout TO 30000")  # 30 seconds
        cursor.close()

    @staticmethod
    @event.listens_for(Engine, 'engine_connect')
    def _ping_connection(connection, branch) -> None:
        """
        Verify connection is still valid on checkout from pool.
        
        Args:
            connection: Database connection
            branch: Branch connection indicator
        """
        if branch:
            return

        try:
            connection.scalar(select([1]))
        except SQLAlchemyError:
            connection.invalidate()
            raise

# Export database configuration
db_config = DatabaseConfig()