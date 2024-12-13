"""
Security configuration module for the Specification Management API.

This module defines security-related settings, JWT configurations, and security headers
for the application. It implements security controls including rate limiting,
session management, and authentication parameters.

Version: 1.0
"""

import os
from datetime import datetime, timedelta
from config.settings import Config

class SecurityConfig:
    """
    Security configuration class containing security-related settings and constants.
    Implements security controls and headers based on technical specifications.
    """

    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv('JWT_SECRET_KEY', Config.SECRET_KEY)
    JWT_ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '1440'))  # 24 hours

    # Rate Limiting Configuration
    RATE_LIMIT_PER_HOUR: int = int(os.getenv('RATE_LIMIT_PER_HOUR', '1000'))
    
    # Brute Force Protection
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv('MAX_LOGIN_ATTEMPTS', '5'))
    LOGIN_ATTEMPT_LOCKOUT_MINUTES: int = int(os.getenv('LOGIN_ATTEMPT_LOCKOUT_MINUTES', '15'))

    # Security Headers Configuration
    SECURITY_HEADERS: dict = {
        # Prevent clickjacking attacks
        'X-Frame-Options': 'DENY',
        
        # Prevent MIME type sniffing
        'X-Content-Type-Options': 'nosniff',
        
        # Enable XSS filtering
        'X-XSS-Protection': '1; mode=block',
        
        # Force HTTPS
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        
        # Content Security Policy
        'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self';",
        
        # Referrer Policy
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        
        # Permissions Policy
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    }

    @classmethod
    def get_token_expiry(cls) -> datetime:
        """
        Calculate token expiration datetime based on configured expiration minutes.

        Returns:
            datetime: UTC datetime when token will expire
        """
        return datetime.utcnow() + timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)

    @classmethod
    def get_lockout_expiry(cls) -> datetime:
        """
        Calculate account lockout expiration datetime.

        Returns:
            datetime: UTC datetime when account lockout will expire
        """
        return datetime.utcnow() + timedelta(minutes=cls.LOGIN_ATTEMPT_LOCKOUT_MINUTES)

    @classmethod
    def validate_rate_limit(cls, request_count: int) -> bool:
        """
        Validate if the request count is within rate limit.

        Args:
            request_count (int): Number of requests made in the current hour

        Returns:
            bool: True if within limit, False otherwise
        """
        return request_count <= cls.RATE_LIMIT_PER_HOUR

    @classmethod
    def should_lockout_account(cls, failed_attempts: int) -> bool:
        """
        Determine if account should be locked based on failed login attempts.

        Args:
            failed_attempts (int): Number of consecutive failed login attempts

        Returns:
            bool: True if account should be locked, False otherwise
        """
        return failed_attempts >= cls.MAX_LOGIN_ATTEMPTS