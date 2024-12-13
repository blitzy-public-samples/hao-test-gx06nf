"""
Core module initialization for the Specification Management API.

This module serves as the main entry point for core functionality, exposing essential
components and utilities from core submodules including:
- Logging and request tracking
- Security and authentication
- Cache management
- Database operations

Version: 1.0
"""

# Import core components
from core.logging import RequestLogger, get_request_id
from core.security import SecurityManager
from core.cache import CacheManager, get_cache, set_cache, delete_cache, clear_cache_pattern
from core.database import DatabaseManager, session_scope, get_session

# Initialize core managers
security_manager = SecurityManager()
database_manager = DatabaseManager()

# Security function exports
def verify_password(password: str, salt: bytes, hash_value: bytes) -> bool:
    """Verify password using secure comparison."""
    return security_manager.verify_password(password, salt, hash_value)

def create_access_token(user_id: str, expiry: datetime) -> str:
    """Create JWT access token for user."""
    return security_manager.create_token(user_id, expiry)

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode JWT token."""
    return security_manager.verify_token(token)

def encrypt_data(data: bytes) -> Tuple[bytes, bytes, bytes]:
    """Encrypt data using AES-256-GCM."""
    return security_manager.encrypt_data(data)

def decrypt_data(encrypted_data: bytes, nonce: bytes, tag: bytes) -> bytes:
    """Decrypt data using AES-256-GCM."""
    return security_manager.decrypt_data(encrypted_data, nonce, tag)

# Database function exports
def get_db() -> Generator[Session, None, None]:
    """Get database session context manager."""
    return session_scope()

def init_db() -> None:
    """Initialize database connections."""
    database_manager.get_session()

def close_db() -> None:
    """Close all database connections."""
    database_manager.close_connections()

# Export core components and utilities
__all__ = [
    # Classes
    "RequestLogger",
    "SecurityManager",
    "CacheManager",
    "DatabaseManager",
    
    # Security functions
    "verify_password",
    "create_access_token", 
    "verify_token",
    "encrypt_data",
    "decrypt_data",
    
    # Cache functions
    "get_cache",
    "set_cache", 
    "delete_cache",
    "clear_cache_pattern",
    
    # Database functions
    "get_db",
    "init_db",
    "close_db",
    
    # Utility functions
    "get_request_id"
]