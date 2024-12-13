"""
Google OAuth2 authentication client implementation with enhanced security features.

This module provides a secure and robust implementation of Google OAuth2 authentication
with rate limiting, token caching, and comprehensive error handling.

Version: 1.0
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging
from dataclasses import dataclass
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from config.security import SecurityConfig
from utils.constants import AUTH_CONSTANTS, ERROR_MESSAGES, HTTP_STATUS_CODES

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class AuthenticationError(Exception):
    """Custom exception for authentication-related errors."""
    message: str
    status_code: int = HTTP_STATUS_CODES['UNAUTHORIZED']

@dataclass
class ProfileError(Exception):
    """Custom exception for profile retrieval errors."""
    message: str
    status_code: int = HTTP_STATUS_CODES['BAD_REQUEST']

class GoogleAuthClient:
    """
    Enhanced client for handling Google OAuth2 authentication with security features.
    
    Implements rate limiting, token caching, and comprehensive error handling for
    Google Cloud User Store authentication.
    """

    def __init__(self) -> None:
        """Initialize Google OAuth client with security configurations."""
        self._client_id = os.getenv('GOOGLE_CLIENT_ID')
        self._client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self._login_attempts: Dict[str, list] = {}
        
        # Validate credentials
        if not self._client_id or not self._client_secret:
            raise ValueError("Google OAuth credentials not properly configured")
            
        # Configure requests session with retry logic
        self._session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        self._session.mount('https://', HTTPAdapter(max_retries=retry_strategy))

    def verify_oauth_token(self, token: str) -> Dict[str, Any]:
        """
        Verify Google OAuth token with rate limiting and security checks.
        
        Args:
            token (str): The OAuth token to verify
            
        Returns:
            Dict[str, Any]: Verified token information with user details
            
        Raises:
            AuthenticationError: If token verification fails or rate limit exceeded
        """
        try:
            # Extract user ID from token for rate limiting
            unverified_claims = id_token.decode_unverified_header(token)
            user_id = unverified_claims.get('sub', '')
            
            # Check rate limiting
            if not self._check_login_attempts(user_id):
                raise AuthenticationError(
                    message=ERROR_MESSAGES['AUTH_LOCKOUT'],
                    status_code=HTTP_STATUS_CODES['RATE_LIMITED']
                )
            
            # Verify token with Google
            id_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                self._client_id
            )
            
            # Validate token claims
            if id_info['aud'] != self._client_id:
                raise AuthenticationError("Invalid audience in token")
                
            if id_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise AuthenticationError("Invalid token issuer")
                
            # Update login attempts on successful verification
            self._update_login_attempts(user_id, success=True)
            
            logger.info(f"Successfully verified token for user: {user_id}")
            return id_info
            
        except ValueError as e:
            # Update failed login attempts
            if user_id:
                self._update_login_attempts(user_id, success=False)
            logger.error(f"Token verification failed: {str(e)}")
            raise AuthenticationError(
                message=ERROR_MESSAGES['INVALID_TOKEN'],
                status_code=HTTP_STATUS_CODES['UNAUTHORIZED']
            )

    def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """
        Retrieve user profile information from Google with enhanced security.
        
        Args:
            access_token (str): Valid Google OAuth access token
            
        Returns:
            Dict[str, Any]: User profile information
            
        Raises:
            ProfileError: If profile retrieval fails
        """
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            response = self._session.get(
                'https://www.googleapis.com/oauth2/v3/userinfo',
                headers=headers,
                timeout=10
            )
            
            if response.status_code != HTTP_STATUS_CODES['OK']:
                raise ProfileError(f"Failed to retrieve profile: {response.text}")
                
            profile_data = response.json()
            
            # Validate required fields
            required_fields = ['sub', 'email']
            if not all(field in profile_data for field in required_fields):
                raise ProfileError("Incomplete profile information received")
                
            logger.info(f"Successfully retrieved profile for user: {profile_data['sub']}")
            return {
                'google_id': profile_data['sub'],
                'email': profile_data['email'],
                'email_verified': profile_data.get('email_verified', False),
                'name': profile_data.get('name'),
                'picture': profile_data.get('picture')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Profile retrieval failed: {str(e)}")
            raise ProfileError("Failed to retrieve user profile")

    def _check_login_attempts(self, user_id: str) -> bool:
        """
        Check if login attempts are within acceptable limits.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            bool: True if login attempt is allowed, False otherwise
        """
        current_time = datetime.utcnow()
        lockout_duration = timedelta(minutes=SecurityConfig.LOGIN_ATTEMPT_LOCKOUT_MINUTES)
        
        # Clean up expired attempts
        self._cleanup_expired_attempts(current_time)
        
        # Get attempts for user
        attempts = self._login_attempts.get(user_id, [])
        
        # Check number of recent failed attempts
        recent_attempts = [
            attempt for attempt in attempts
            if current_time - attempt['timestamp'] < lockout_duration
        ]
        
        if len(recent_attempts) >= SecurityConfig.MAX_LOGIN_ATTEMPTS:
            logger.warning(f"Login attempts exceeded for user: {user_id}")
            return False
            
        return True

    def _update_login_attempts(self, user_id: str, success: bool) -> None:
        """
        Update login attempts tracking for a user.
        
        Args:
            user_id (str): User identifier
            success (bool): Whether the login attempt was successful
        """
        current_time = datetime.utcnow()
        
        if user_id not in self._login_attempts:
            self._login_attempts[user_id] = []
            
        if not success:
            self._login_attempts[user_id].append({
                'timestamp': current_time,
                'success': False
            })
            
        # Reset attempts on successful login
        if success:
            self._login_attempts[user_id] = []

    def _cleanup_expired_attempts(self, current_time: datetime) -> None:
        """
        Clean up expired login attempts.
        
        Args:
            current_time (datetime): Current UTC timestamp
        """
        lockout_duration = timedelta(minutes=SecurityConfig.LOGIN_ATTEMPT_LOCKOUT_MINUTES)
        
        for user_id in list(self._login_attempts.keys()):
            self._login_attempts[user_id] = [
                attempt for attempt in self._login_attempts[user_id]
                if current_time - attempt['timestamp'] < lockout_duration
            ]
            
            # Remove empty entries
            if not self._login_attempts[user_id]:
                del self._login_attempts[user_id]