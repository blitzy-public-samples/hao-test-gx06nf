"""
Central constants module containing system-wide configuration values, limits, and settings.

This module defines all the constant values used across the application, including:
- Database constraints and limits
- Authentication and security settings
- Rate limiting configuration
- Cache TTLs
- API configuration
- HTTP status codes
- Error messages

All constants are defined as Final types to ensure immutability during runtime.
Version: 1.0
"""

from typing import Final, TypedDict, List

# Database Constants
class DatabaseConstantsType(TypedDict):
    """Type definition for database-related constants."""
    MAX_ITEMS_PER_SPECIFICATION: int
    MAX_TITLE_LENGTH: int
    MAX_CONTENT_LENGTH: int
    MIN_ORDER_INDEX: int
    MAX_ORDER_INDEX: int
    MAX_SPECIFICATIONS_PER_PROJECT: int

DATABASE_CONSTANTS: Final[DatabaseConstantsType] = {
    'MAX_ITEMS_PER_SPECIFICATION': 10,  # Maximum items allowed per specification
    'MAX_TITLE_LENGTH': 255,  # Maximum length for titles (projects, specs)
    'MAX_CONTENT_LENGTH': 1000,  # Maximum length for content fields
    'MIN_ORDER_INDEX': 0,  # Minimum value for order indexing
    'MAX_ORDER_INDEX': 1000,  # Maximum value for order indexing
    'MAX_SPECIFICATIONS_PER_PROJECT': 100  # Maximum specifications per project
}

# Authentication Constants
class AuthConstantsType(TypedDict):
    """Type definition for authentication-related constants."""
    JWT_EXPIRY_HOURS: int
    TOKEN_ALGORITHM: str
    BEARER_TOKEN_PREFIX: str
    MAX_FAILED_AUTH_ATTEMPTS: int
    AUTH_LOCKOUT_MINUTES: int
    MIN_TOKEN_LENGTH: int

AUTH_CONSTANTS: Final[AuthConstantsType] = {
    'JWT_EXPIRY_HOURS': 24,  # JWT token expiration time in hours
    'TOKEN_ALGORITHM': 'HS256',  # JWT signing algorithm
    'BEARER_TOKEN_PREFIX': 'Bearer',  # Authorization header prefix
    'MAX_FAILED_AUTH_ATTEMPTS': 5,  # Maximum failed login attempts
    'AUTH_LOCKOUT_MINUTES': 15,  # Account lockout duration in minutes
    'MIN_TOKEN_LENGTH': 32  # Minimum length for security tokens
}

# Rate Limiting Constants
class RateLimitConstantsType(TypedDict):
    """Type definition for rate limiting constants."""
    REQUESTS_PER_HOUR: int
    RATE_LIMIT_WINDOW_SECONDS: int
    BURST_LIMIT: int
    RATE_LIMIT_ALERT_THRESHOLD: float

RATE_LIMIT_CONSTANTS: Final[RateLimitConstantsType] = {
    'REQUESTS_PER_HOUR': 1000,  # Maximum requests per hour per user
    'RATE_LIMIT_WINDOW_SECONDS': 3600,  # Rate limit window in seconds
    'BURST_LIMIT': 50,  # Maximum burst requests allowed
    'RATE_LIMIT_ALERT_THRESHOLD': 0.9  # Alert threshold for rate limit (90%)
}

# Cache Constants
class CacheConstantsType(TypedDict):
    """Type definition for cache-related constants."""
    PROJECT_CACHE_TTL: int
    SPECIFICATION_CACHE_TTL: int
    ITEMS_CACHE_TTL: int
    USER_CACHE_TTL: int
    TOKEN_CACHE_TTL: int
    CACHE_KEY_PREFIX: str

CACHE_CONSTANTS: Final[CacheConstantsType] = {
    'PROJECT_CACHE_TTL': 300,  # Project cache TTL in seconds (5 minutes)
    'SPECIFICATION_CACHE_TTL': 120,  # Specification cache TTL (2 minutes)
    'ITEMS_CACHE_TTL': 120,  # Items cache TTL (2 minutes)
    'USER_CACHE_TTL': 900,  # User data cache TTL (15 minutes)
    'TOKEN_CACHE_TTL': 86400,  # Token cache TTL (24 hours)
    'CACHE_KEY_PREFIX': 'spec_mgmt'  # Cache key prefix for the application
}

# API Constants
class ApiConstantsType(TypedDict):
    """Type definition for API-related constants."""
    API_VERSION: str
    DEFAULT_PAGE_SIZE: int
    MAX_PAGE_SIZE: int
    MIN_PAGE_SIZE: int
    DEFAULT_SORT_ORDER: str
    VALID_SORT_ORDERS: List[str]

API_CONSTANTS: Final[ApiConstantsType] = {
    'API_VERSION': 'v1',  # API version identifier
    'DEFAULT_PAGE_SIZE': 20,  # Default items per page
    'MAX_PAGE_SIZE': 100,  # Maximum items per page
    'MIN_PAGE_SIZE': 1,  # Minimum items per page
    'DEFAULT_SORT_ORDER': 'asc',  # Default sort order
    'VALID_SORT_ORDERS': ['asc', 'desc']  # Valid sort order values
}

# HTTP Status Codes
class HttpStatusCodesType(TypedDict):
    """Type definition for HTTP status codes."""
    OK: int
    CREATED: int
    NO_CONTENT: int
    BAD_REQUEST: int
    UNAUTHORIZED: int
    FORBIDDEN: int
    NOT_FOUND: int
    RATE_LIMITED: int
    SERVER_ERROR: int
    SERVICE_UNAVAILABLE: int

HTTP_STATUS_CODES: Final[HttpStatusCodesType] = {
    'OK': 200,
    'CREATED': 201,
    'NO_CONTENT': 204,
    'BAD_REQUEST': 400,
    'UNAUTHORIZED': 401,
    'FORBIDDEN': 403,
    'NOT_FOUND': 404,
    'RATE_LIMITED': 429,
    'SERVER_ERROR': 500,
    'SERVICE_UNAVAILABLE': 503
}

# Error Messages
class ErrorMessagesType(TypedDict):
    """Type definition for error messages."""
    INVALID_TOKEN: str
    UNAUTHORIZED_ACCESS: str
    RESOURCE_NOT_FOUND: str
    RATE_LIMIT_EXCEEDED: str
    MAX_ITEMS_REACHED: str
    INVALID_ORDER_INDEX: str
    PROJECT_ACCESS_DENIED: str
    INVALID_PAGE_SIZE: str
    INVALID_SORT_ORDER: str
    AUTH_LOCKOUT: str

ERROR_MESSAGES: Final[ErrorMessagesType] = {
    'INVALID_TOKEN': 'Invalid or expired authentication token',
    'UNAUTHORIZED_ACCESS': 'Unauthorized access to resource',
    'RESOURCE_NOT_FOUND': 'Requested resource not found',
    'RATE_LIMIT_EXCEEDED': 'Rate limit exceeded. Please try again later',
    'MAX_ITEMS_REACHED': 'Maximum number of items (10) reached for specification',
    'INVALID_ORDER_INDEX': 'Order index must be between 0 and 1000',
    'PROJECT_ACCESS_DENIED': 'Access denied to project',
    'INVALID_PAGE_SIZE': 'Page size must be between 1 and 100',
    'INVALID_SORT_ORDER': "Sort order must be either 'asc' or 'desc'",
    'AUTH_LOCKOUT': 'Account temporarily locked due to multiple failed attempts'
}