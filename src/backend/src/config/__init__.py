"""
Configuration initialization module for the Specification Management API.

This module aggregates and exports all configuration settings with comprehensive validation,
including environment-specific configurations, logging, security, caching, and database settings.

Version: 1.0.0
"""

import os
from typing import Dict, Type, Any, Optional

from config.settings import DevelopmentConfig, ProductionConfig
from config.logging import setup_logging
from config.security import SecurityConfig
from config.cache import CacheConfig
from config.database import DatabaseConfig

# Environment configuration
ENV: str = os.getenv('FLASK_ENV', 'development')
CONFIG_VERSION: str = '1.0.0'

# Environment-specific configuration mapping
config_by_env: Dict[str, Type[Any]] = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}

class ConfigurationError(Exception):
    """Custom exception for configuration validation errors."""
    pass

def validate_config(config: dict) -> bool:
    """
    Validates configuration dependencies and settings.
    
    Args:
        config (dict): Configuration dictionary to validate
        
    Returns:
        bool: True if configuration is valid
        
    Raises:
        ConfigurationError: If configuration validation fails
    """
    try:
        # Validate security header configuration
        if not config.get('SECURITY_HEADERS'):
            raise ConfigurationError("Security headers configuration is required")
        
        required_headers = ['X-Frame-Options', 'X-Content-Type-Options', 
                          'X-XSS-Protection', 'Strict-Transport-Security']
        missing_headers = [header for header in required_headers 
                         if header not in config['SECURITY_HEADERS']]
        if missing_headers:
            raise ConfigurationError(f"Missing required security headers: {missing_headers}")
        
        # Validate JWT configuration
        jwt_config = config.get('JWT_CONFIG', {})
        required_jwt = ['JWT_SECRET_KEY', 'JWT_ACCESS_TOKEN_EXPIRES']
        missing_jwt = [key for key in required_jwt if key not in jwt_config]
        if missing_jwt:
            raise ConfigurationError(f"Missing required JWT configuration: {missing_jwt}")
            
        # Validate cache configuration
        cache_config = config.get('CACHE_CONFIG', {})
        if not cache_config.get('CACHE_TYPE'):
            raise ConfigurationError("Cache type configuration is required")
            
        # Validate database configuration
        if not config.get('SQLALCHEMY_DATABASE_URI'):
            raise ConfigurationError("Database URI configuration is required")
            
        # Production-specific validations
        if ENV == 'production':
            # Validate SSL configuration
            ssl_config = config.get('SSL_CONFIG', {})
            if not ssl_config:
                raise ConfigurationError("SSL configuration is required in production")
                
            # Validate rate limiting
            rate_limit = config.get('RATE_LIMIT_CONFIG', {})
            if not rate_limit.get('ENABLED'):
                raise ConfigurationError("Rate limiting must be enabled in production")
                
        return True
        
    except Exception as e:
        raise ConfigurationError(f"Configuration validation failed: {str(e)}")

def init_app_config(app) -> None:
    """
    Initialize and configure all application components with validation.
    
    Args:
        app: Flask application instance
        
    Raises:
        ConfigurationError: If configuration initialization fails
    """
    try:
        # Load environment-specific configuration
        config_class = config_by_env.get(ENV)
        if not config_class:
            raise ConfigurationError(f"Invalid environment: {ENV}")
        
        # Initialize configuration instances
        security_config = SecurityConfig()
        cache_config = CacheConfig()
        db_config = DatabaseConfig()
        
        # Merge configurations
        config = {
            **config_class.__dict__,
            'SECURITY_HEADERS': security_config.SECURITY_HEADERS,
            'JWT_CONFIG': security_config.JWT_CONFIG,
            'RATE_LIMIT_CONFIG': security_config.RATE_LIMIT_CONFIG,
            'CACHE_CONFIG': cache_config.CACHE_REDIS_CONFIG,
            'CACHE_TTL_CONFIG': cache_config.CACHE_TTL,
            'SQLALCHEMY_DATABASE_URI': db_config.SQLALCHEMY_DATABASE_URI,
            'SQLALCHEMY_ENGINE_OPTIONS': db_config.SQLALCHEMY_ENGINE_OPTIONS,
            'SSL_CONFIG': getattr(db_config, 'SSL_CONFIG', {})
        }
        
        # Validate merged configuration
        validate_config(config)
        
        # Initialize logging
        setup_logging()
        
        # Apply configuration to Flask app
        app.config.update(config)
        
        # Set security headers
        @app.after_request
        def add_security_headers(response):
            """Add security headers to all responses."""
            for header, value in config['SECURITY_HEADERS'].items():
                response.headers[header] = value
            return response
            
    except Exception as e:
        raise ConfigurationError(f"Failed to initialize application configuration: {str(e)}")

# Export configuration utilities and version
__all__ = ['init_app_config', 'config_by_env', 'CONFIG_VERSION']