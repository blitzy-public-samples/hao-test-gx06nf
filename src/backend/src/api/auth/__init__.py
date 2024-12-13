"""
Authentication module initialization providing centralized access to authentication components.

This module serves as the main entry point for all authentication-related functionality,
ensuring consistent security controls and token management across the application.
Implements JWT management, Google OAuth integration, and middleware components.

Version: 1.0
"""

# Import JWT token management functions
from api.auth.jwt import (  # version: 2.0+
    create_access_token,
    create_refresh_token, 
    refresh_access_token
)

# Import Google OAuth verification functions
from api.auth.google import (  # version: 1.0
    verify_google_oauth_token,
    get_google_user_info
)

# Import authentication middleware
from api.auth.middleware import (  # version: 1.0
    AuthMiddleware
)

# Constants for authentication headers
AUTH_TOKEN_HEADER = 'Authorization'
AUTH_TOKEN_TYPE = 'Bearer'

# Export authentication components
__all__ = [
    # JWT token management
    'create_access_token',
    'create_refresh_token',
    'refresh_access_token',
    
    # Google OAuth integration
    'verify_google_oauth_token',
    'get_google_user_info',
    
    # Authentication middleware
    'AuthMiddleware',
    
    # Authentication constants
    'AUTH_TOKEN_HEADER',
    'AUTH_TOKEN_TYPE'
]

# Module metadata
__version__ = '1.0'
__author__ = 'Specification Management API Team'