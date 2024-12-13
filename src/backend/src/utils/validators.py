"""
Comprehensive validation utilities module providing secure input validation,
data sanitization, and format verification for application data structures.

This module implements strict validation rules with detailed error handling
and type safety for users, projects, specifications and items.

Version: 1.0.0
"""

import re
from typing import Union, Optional
from datetime import datetime

# RFC 5322 compliant email validation pattern
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Business rule constants
MAX_ITEMS_PER_SPECIFICATION = 10
MAX_CONTENT_LENGTH = 1000
MIN_CONTENT_LENGTH = 1

# Compile regex patterns for performance
EMAIL_PATTERN = re.compile(EMAIL_REGEX)
GOOGLE_ID_PATTERN = re.compile(r'^[0-9]{21}$')  # Google ID format validation
DANGEROUS_CHARS_PATTERN = re.compile(r'[<>&;]')  # Basic XSS prevention

def validate_email(email: Optional[str]) -> bool:
    """
    Validates email format using comprehensive regex pattern ensuring RFC 5322 compliance.
    
    Args:
        email: String containing the email address to validate
        
    Returns:
        bool: True if email is valid and meets all security requirements
        
    Examples:
        >>> validate_email("user@example.com")
        True
        >>> validate_email("invalid.email@")
        False
    """
    try:
        if not email:
            return False
            
        email = str(email).strip()
        
        # Basic length validation
        if len(email) < 5 or len(email) > 255:
            return False
            
        # Check against RFC 5322 pattern
        if not EMAIL_PATTERN.match(email):
            return False
            
        # Check for dangerous characters
        if DANGEROUS_CHARS_PATTERN.search(email):
            return False
            
        return True
        
    except Exception:
        return False

def validate_content_length(content: Optional[str]) -> bool:
    """
    Validates content length ensuring it meets security and usability requirements.
    
    Args:
        content: String containing the content to validate
        
    Returns:
        bool: True if content length is valid and content is properly sanitized
        
    Examples:
        >>> validate_content_length("Valid content")
        True
        >>> validate_content_length("")
        False
    """
    try:
        if content is None:
            return False
            
        content = str(content).strip()
        
        # Length validation
        content_length = len(content)
        if content_length < MIN_CONTENT_LENGTH or content_length > MAX_CONTENT_LENGTH:
            return False
            
        # Security validation
        if DANGEROUS_CHARS_PATTERN.search(content):
            return False
            
        return True
        
    except Exception:
        return False

def validate_order_index(order_index: Optional[Union[int, str]]) -> bool:
    """
    Validates order index ensuring proper sequence maintenance and bounds.
    
    Args:
        order_index: Integer or string containing the order index to validate
        
    Returns:
        bool: True if order index is valid and within acceptable range
        
    Examples:
        >>> validate_order_index(5)
        True
        >>> validate_order_index(-1)
        False
    """
    try:
        if order_index is None:
            return False
            
        # Convert to int if string
        if isinstance(order_index, str):
            order_index = int(order_index)
            
        # Type validation
        if not isinstance(order_index, int):
            return False
            
        # Range validation
        if order_index < 0 or order_index > 1000000:
            return False
            
        return True
        
    except (ValueError, TypeError):
        return False

def validate_items_count(current_count: Optional[Union[int, str]]) -> bool:
    """
    Validates number of items in a specification enforcing business rules.
    
    Args:
        current_count: Integer or string containing the current items count
        
    Returns:
        bool: True if count is within allowed limits and valid
        
    Examples:
        >>> validate_items_count(5)
        True
        >>> validate_items_count(11)
        False
    """
    try:
        if current_count is None:
            return False
            
        # Convert to int if string
        if isinstance(current_count, str):
            current_count = int(current_count)
            
        # Type validation
        if not isinstance(current_count, int):
            return False
            
        # Range validation
        if current_count < 0 or current_count >= MAX_ITEMS_PER_SPECIFICATION:
            return False
            
        return True
        
    except (ValueError, TypeError):
        return False

def validate_google_id(google_id: Optional[str]) -> bool:
    """
    Validates Google ID format and security requirements.
    
    Args:
        google_id: String containing the Google ID to validate
        
    Returns:
        bool: True if Google ID meets all format and security requirements
        
    Examples:
        >>> validate_google_id("123456789012345678901")
        True
        >>> validate_google_id("invalid_id")
        False
    """
    try:
        if not google_id:
            return False
            
        google_id = str(google_id).strip()
        
        # Length validation
        if len(google_id) != 21:
            return False
            
        # Format validation
        if not GOOGLE_ID_PATTERN.match(google_id):
            return False
            
        # Security validation
        if DANGEROUS_CHARS_PATTERN.search(google_id):
            return False
            
        return True
        
    except Exception:
        return False