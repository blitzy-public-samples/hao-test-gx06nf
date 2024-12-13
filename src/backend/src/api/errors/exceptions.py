"""
Custom exception classes for handling API errors with consistent error responses.

This module defines a hierarchy of exception classes that map to specific HTTP status codes
and provide standardized error handling patterns across the API.

Version: 1.0
"""

from datetime import datetime
from typing import Dict, Optional
from werkzeug.exceptions import HTTPException  # version 2.0+


class APIException(HTTPException):
    """
    Base exception class for all API-specific errors providing standardized error handling.
    
    Extends werkzeug's HTTPException to provide consistent error response format with
    error code, message, details and timestamp across all API errors.
    """

    def __init__(self, message: str, status_code: int, details: Optional[Dict] = None) -> None:
        """
        Initialize API exception with standardized error attributes.

        Args:
            message (str): Human readable error message
            status_code (int): HTTP status code for the error
            details (Optional[Dict]): Additional error context and details
        
        Raises:
            ValueError: If message is empty/None or status_code is invalid
        """
        if not message:
            raise ValueError("Error message cannot be empty")
        if not isinstance(status_code, int) or status_code < 100 or status_code >= 600:
            raise ValueError("Invalid HTTP status code")

        super().__init__(description=message, response=None)
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        """
        Convert exception to standardized error response dictionary.

        Returns:
            Dict: Formatted error response with code, message, details and timestamp
        """
        return {
            "error": {
                "code": self.status_code,
                "message": self.message,
                "details": self.details,
                "timestamp": self.timestamp
            }
        }


class ValidationError(APIException):
    """
    Exception for request validation failures.
    
    Maps to HTTP 400 Bad Request status code and includes validation error details.
    """

    def __init__(self, message: str, details: Optional[Dict] = None) -> None:
        """
        Initialize validation error with specific details.

        Args:
            message (str): Validation error description
            details (Optional[Dict]): Validation failure specifics
        """
        super().__init__(
            message=message,
            status_code=400,
            details=details
        )


class AuthenticationError(APIException):
    """
    Exception for authentication failures.
    
    Maps to HTTP 401 Unauthorized status code for invalid or missing authentication.
    """

    def __init__(self, message: str = "Authentication required") -> None:
        """
        Initialize authentication error.

        Args:
            message (str): Authentication error description
        """
        super().__init__(
            message=message,
            status_code=401,
            details={"error_code": "UNAUTHORIZED"}
        )


class AuthorizationError(APIException):
    """
    Exception for authorization failures.
    
    Maps to HTTP 403 Forbidden status code for insufficient permissions.
    """

    def __init__(self, message: str = "Insufficient permissions") -> None:
        """
        Initialize authorization error.

        Args:
            message (str): Authorization error description
        """
        super().__init__(
            message=message,
            status_code=403,
            details={"error_code": "FORBIDDEN"}
        )


class NotFoundError(APIException):
    """
    Exception for resource not found errors.
    
    Maps to HTTP 404 Not Found status code when requested resources don't exist.
    """

    def __init__(self, message: str = "Resource not found") -> None:
        """
        Initialize not found error.

        Args:
            message (str): Resource not found description
        """
        super().__init__(
            message=message,
            status_code=404,
            details={"error_code": "NOT_FOUND"}
        )


class RateLimitError(APIException):
    """
    Exception for rate limit exceeded errors.
    
    Maps to HTTP 429 Too Many Requests status code when rate limits are exceeded.
    """

    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None) -> None:
        """
        Initialize rate limit error.

        Args:
            message (str): Rate limit error description
            retry_after (Optional[int]): Seconds until next request is allowed
        """
        details = {
            "error_code": "RATE_LIMITED"
        }
        if retry_after is not None:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            status_code=429,
            details=details
        )