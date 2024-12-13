"""
Core configuration module for the Specification Management API.

This module provides environment-specific configuration classes and utilities
for managing application settings across different deployment environments.
It includes comprehensive security, caching, and database configurations.

Version: 1.0
"""

import os
from pathlib import Path
from typing import Dict, Any, Type, Optional, Final
from dataclasses import dataclass

from utils.constants import (
    DATABASE_CONSTANTS,
    RATE_LIMIT_CONSTANTS,
    CACHE_CONSTANTS,
)

# Global Constants
ENV: Final[str] = os.getenv('FLASK_ENV', 'development')
DEBUG: Final[bool] = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
SECRET_KEY: Final[str] = os.getenv('SECRET_KEY', 'your-secret-key-here')
PROJECT_ROOT: Final[Path] = Path(__file__).parent.parent.parent
RATE_LIMIT_ENABLED: Final[bool] = os.getenv('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
CACHE_ENABLED: Final[bool] = os.getenv('CACHE_ENABLED', 'True').lower() == 'true'

@dataclass
class Config:
    """Base configuration class with common settings."""
    
    ENV: str = ENV
    DEBUG: bool = DEBUG
    TESTING: bool = False
    SECRET_KEY: str = SECRET_KEY
    PROJECT_ROOT: Path = PROJECT_ROOT
    
    # Flask-SQLAlchemy settings
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: Dict[str, Any] = {
        'pool_size': 10,
        'pool_timeout': 30,
        'pool_recycle': 1800,
    }
    
    # Cache configuration
    CACHE_CONFIG: Dict[str, Any] = {
        'CACHE_TYPE': 'simple',
        'CACHE_DEFAULT_TIMEOUT': CACHE_CONSTANTS['PROJECT_CACHE_TTL'],
        'CACHE_KEY_PREFIX': 'spec_mgmt_',
        'CACHE_REDIS_URL': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    }
    
    # Rate limiting configuration
    RATE_LIMIT_CONFIG: Dict[str, Any] = {
        'ENABLED': RATE_LIMIT_ENABLED,
        'REQUESTS_PER_HOUR': RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR'],
        'STORAGE_URL': os.getenv('RATE_LIMIT_STORAGE_URL', 'memory://'),
    }
    
    # JWT configuration
    JWT_CONFIG: Dict[str, Any] = {
        'JWT_SECRET_KEY': SECRET_KEY,
        'JWT_ACCESS_TOKEN_EXPIRES': 24 * 3600,  # 24 hours
        'JWT_REFRESH_TOKEN_EXPIRES': 30 * 24 * 3600,  # 30 days
        'JWT_ERROR_MESSAGE_KEY': 'message',
    }
    
    # Security headers
    SECURITY_HEADERS: Dict[str, Any] = {
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    }


class ProductionConfig(Config):
    """Production environment configuration with strict security settings."""
    
    DEBUG: bool = False
    TESTING: bool = False
    
    # SSL configuration
    SSL_CONFIG: Dict[str, Any] = {
        'PREFERRED_URL_SCHEME': 'https',
        'SESSION_COOKIE_SECURE': True,
        'REMEMBER_COOKIE_SECURE': True,
    }
    
    # Production cache configuration
    CACHE_CONFIG: Dict[str, Any] = {
        **Config.CACHE_CONFIG,
        'CACHE_TYPE': 'redis',
        'CACHE_REDIS_URL': os.environ['REDIS_URL'],
    }
    
    # Production rate limiting
    RATE_LIMIT_CONFIG: Dict[str, Any] = {
        **Config.RATE_LIMIT_CONFIG,
        'STORAGE_URL': os.environ['RATE_LIMIT_STORAGE_URL'],
    }
    
    # Production database configuration
    SQLALCHEMY_DATABASE_URI: str = os.environ['DATABASE_URL']
    SQLALCHEMY_ENGINE_OPTIONS: Dict[str, Any] = {
        **Config.SQLALCHEMY_ENGINE_OPTIONS,
        'pool_size': 20,
        'max_overflow': 5,
    }
    
    # Content Security Policy
    SECURITY_HEADERS: Dict[str, Any] = {
        **Config.SECURITY_HEADERS,
        'Content-Security-Policy': (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self';"
        ),
    }


class DevelopmentConfig(Config):
    """Development environment configuration with debug settings."""
    
    DEBUG: bool = True
    TESTING: bool = False
    
    # Development database configuration
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/spec_mgmt_dev'
    )
    
    # Development cache configuration
    CACHE_CONFIG: Dict[str, Any] = {
        **Config.CACHE_CONFIG,
        'CACHE_TYPE': 'simple',
    }
    
    # CORS settings for development
    CORS_SETTINGS: Dict[str, Any] = {
        'CORS_ORIGINS': '*',
        'CORS_METHODS': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        'CORS_ALLOW_HEADERS': ['Content-Type', 'Authorization'],
    }


class TestingConfig(Config):
    """Testing environment configuration with in-memory settings."""
    
    DEBUG: bool = True
    TESTING: bool = True
    
    # Test database configuration
    SQLALCHEMY_DATABASE_URI: str = 'sqlite:///:memory:'
    
    # Test cache configuration
    CACHE_CONFIG: Dict[str, Any] = {
        **Config.CACHE_CONFIG,
        'CACHE_TYPE': 'simple',
    }
    
    # Disable rate limiting for tests
    RATE_LIMIT_CONFIG: Dict[str, Any] = {
        **Config.RATE_LIMIT_CONFIG,
        'ENABLED': False,
    }


def get_config() -> Type[Config]:
    """
    Factory function to get the appropriate configuration based on the environment.
    
    Returns:
        Type[Config]: Configuration class for the current environment
    
    Raises:
        ValueError: If an invalid environment is specified
    """
    config_map: Dict[str, Type[Config]] = {
        'production': ProductionConfig,
        'development': DevelopmentConfig,
        'testing': TestingConfig,
    }
    
    config_class = config_map.get(ENV)
    if not config_class:
        raise ValueError(f"Invalid environment: {ENV}")
    
    validate_config(config_class)
    return config_class


def validate_config(config_class: Type[Config]) -> bool:
    """
    Validates the configuration settings for the given environment.
    
    Args:
        config_class: Configuration class to validate
    
    Returns:
        bool: True if configuration is valid
    
    Raises:
        ValueError: If configuration validation fails
    """
    if ENV == 'production':
        required_vars = [
            'DATABASE_URL',
            'REDIS_URL',
            'SECRET_KEY',
            'RATE_LIMIT_STORAGE_URL',
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables for production: {', '.join(missing_vars)}"
            )
        
        if os.getenv('SECRET_KEY') == 'your-secret-key-here':
            raise ValueError("Production environment requires a secure SECRET_KEY")
    
    return True


# Export configuration classes and utilities
__all__ = [
    'Config',
    'ProductionConfig',
    'DevelopmentConfig',
    'TestingConfig',
    'get_config',
    'validate_config',
]