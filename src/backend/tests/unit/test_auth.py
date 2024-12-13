"""
Unit tests for authentication functionality including JWT token management,
Google OAuth integration, and authentication decorators.

This test module provides comprehensive coverage of:
- JWT token generation, validation, and revocation
- Google OAuth token verification and user profile retrieval
- Authentication decorators and security controls
- Rate limiting and brute force protection

Version: 1.0
"""

import pytest
import jwt
from unittest import mock
from datetime import datetime, timedelta
from freezegun import freeze_time  # version: 1.0+
from flask import Flask, jsonify

from api.auth.jwt import JWTHandler, create_access_token
from api.auth.google import GoogleAuthClient, AuthenticationError, ProfileError
from api.auth.decorators import require_auth
from api.auth.utils import extract_token, is_token_blacklisted
from config.security import SecurityConfig
from utils.constants import AUTH_CONSTANTS, ERROR_MESSAGES, HTTP_STATUS_CODES

def pytest_configure():
    """Configure test environment and dependencies."""
    # Configure test environment variables
    pytest.test_client_id = "test_client_id"
    pytest.test_client_secret = "test_client_secret"
    pytest.test_jwt_secret = "test_jwt_secret_key_with_minimum_length_requirement"

class TestJWTHandler:
    """Test cases for JWT token management functionality."""

    def setup_method(self):
        """Set up test environment for JWT tests."""
        self._jwt_handler = JWTHandler()
        self._test_payload = {
            'sub': 'test_user_id',
            'email': 'test@example.com',
            'name': 'Test User'
        }

    def test_generate_token(self):
        """Test JWT token generation with comprehensive validation."""
        # Generate token with test payload
        token = self._jwt_handler.generate_token(self._test_payload)

        # Verify token is string and properly formatted
        assert isinstance(token, str)
        assert len(token.split('.')) == 3

        # Decode token and validate payload structure
        decoded = jwt.decode(
            token,
            SecurityConfig.JWT_SECRET_KEY,
            algorithms=[SecurityConfig.JWT_ALGORITHM]
        )

        # Verify required claims
        assert decoded['sub'] == self._test_payload['sub']
        assert decoded['email'] == self._test_payload['email']
        assert 'iat' in decoded
        assert 'exp' in decoded
        assert 'type' in decoded
        assert 'fingerprint' in decoded

        # Verify token hasn't expired
        assert decoded['exp'] > datetime.utcnow().timestamp()

    @freeze_time("2024-01-20")
    def test_token_expiry(self):
        """Test JWT token expiration handling with time freezing."""
        # Generate token with 1-hour expiry
        token = create_access_token(
            self._test_payload,
            expires_delta=timedelta(hours=1)
        )

        # Verify token is valid initially
        assert self._jwt_handler.validate_token(token)

        # Move time forward by 2 hours
        with freeze_time("2024-01-20 02:00:00"):
            # Verify token has expired
            with pytest.raises(jwt.InvalidTokenError) as exc_info:
                self._jwt_handler.validate_token(token)
            assert "Token has expired" in str(exc_info.value)

    def test_validate_token(self):
        """Test JWT token validation with security checks."""
        # Generate valid token
        token = self._jwt_handler.generate_token(self._test_payload)

        # Test successful validation
        payload = self._jwt_handler.validate_token(token)
        assert payload['sub'] == self._test_payload['sub']
        assert payload['type'] == 'access'

        # Test invalid token format
        with pytest.raises(jwt.InvalidTokenError):
            self._jwt_handler.validate_token("invalid.token.format")

        # Test tampered token
        tampered_token = token[:-5] + "12345"
        with pytest.raises(jwt.InvalidTokenError):
            self._jwt_handler.validate_token(tampered_token)

        # Test token with invalid signature
        invalid_token = jwt.encode(
            self._test_payload,
            "different_secret",
            algorithm=SecurityConfig.JWT_ALGORITHM
        )
        with pytest.raises(jwt.InvalidTokenError):
            self._jwt_handler.validate_token(invalid_token)

    def test_revoke_token(self):
        """Test JWT token revocation and blacklist management."""
        # Generate token to revoke
        token = self._jwt_handler.generate_token(self._test_payload)

        # Verify token is valid initially
        assert self._jwt_handler.validate_token(token)

        # Revoke token
        assert self._jwt_handler.revoke_token(token)

        # Verify token is now invalid
        with pytest.raises(jwt.InvalidTokenError):
            self._jwt_handler.validate_token(token)

        # Verify token is in blacklist
        assert is_token_blacklisted(token)

        # Test revoking already revoked token
        assert not self._jwt_handler.revoke_token(token)

class TestGoogleAuth:
    """Test cases for Google OAuth authentication functionality."""

    def setup_method(self):
        """Set up test environment for Google auth tests."""
        self._google_client = GoogleAuthClient()
        self._mock_user_profile = {
            'sub': 'test_google_id',
            'email': 'test@example.com',
            'email_verified': True,
            'name': 'Test User',
            'picture': 'https://example.com/photo.jpg'
        }

    @mock.patch('google.oauth2.id_token.verify_oauth2_token')
    def test_verify_oauth_token(self, mock_verify):
        """Test Google OAuth token verification with mocked responses."""
        # Configure mock response
        mock_verify.return_value = {
            'sub': 'test_google_id',
            'email': 'test@example.com',
            'aud': pytest.test_client_id,
            'iss': 'accounts.google.com'
        }

        # Test successful verification
        token = "test_oauth_token"
        result = self._google_client.verify_oauth_token(token)
        assert result['sub'] == 'test_google_id'
        assert result['email'] == 'test@example.com'

        # Test invalid token
        mock_verify.side_effect = ValueError("Invalid token")
        with pytest.raises(AuthenticationError) as exc_info:
            self._google_client.verify_oauth_token("invalid_token")
        assert ERROR_MESSAGES['INVALID_TOKEN'] in str(exc_info.value)

        # Test rate limiting
        for _ in range(SecurityConfig.MAX_LOGIN_ATTEMPTS + 1):
            with pytest.raises(AuthenticationError):
                self._google_client.verify_oauth_token("invalid_token")
        
        # Verify lockout message
        with pytest.raises(AuthenticationError) as exc_info:
            self._google_client.verify_oauth_token(token)
        assert ERROR_MESSAGES['AUTH_LOCKOUT'] in str(exc_info.value)

    @mock.patch('requests.Session.get')
    def test_get_user_profile(self, mock_get):
        """Test user profile retrieval from Google API."""
        # Configure mock response
        mock_response = mock.Mock()
        mock_response.status_code = HTTP_STATUS_CODES['OK']
        mock_response.json.return_value = self._mock_user_profile
        mock_get.return_value = mock_response

        # Test successful profile retrieval
        profile = self._google_client.get_user_profile("test_access_token")
        assert profile['google_id'] == self._mock_user_profile['sub']
        assert profile['email'] == self._mock_user_profile['email']
        assert profile['email_verified'] == self._mock_user_profile['email_verified']

        # Test API error
        mock_response.status_code = HTTP_STATUS_CODES['BAD_REQUEST']
        mock_response.text = "API Error"
        with pytest.raises(ProfileError) as exc_info:
            self._google_client.get_user_profile("invalid_token")
        assert "Failed to retrieve profile" in str(exc_info.value)

        # Test network error
        mock_get.side_effect = Exception("Network error")
        with pytest.raises(ProfileError) as exc_info:
            self._google_client.get_user_profile("test_token")
        assert "Failed to retrieve user profile" in str(exc_info.value)

class TestAuthDecorators:
    """Test cases for authentication decorators."""

    def setup_method(self):
        """Set up test environment for decorator tests."""
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self._jwt_handler = JWTHandler()

        # Configure test routes
        @self.app.route('/protected')
        @require_auth
        def protected_route():
            return jsonify({'message': 'success'})

    def test_require_auth(self):
        """Test authentication decorator functionality."""
        # Test without token
        response = self.client.get('/protected')
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']

        # Test with invalid token
        response = self.client.get(
            '/protected',
            headers={'Authorization': 'Bearer invalid.token.here'}
        )
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']

        # Test with valid token
        token = self._jwt_handler.generate_token({
            'sub': 'test_user',
            'email': 'test@example.com'
        })
        response = self.client.get(
            '/protected',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == HTTP_STATUS_CODES['OK']
        assert response.json['message'] == 'success'

        # Test with blacklisted token
        self._jwt_handler.revoke_token(token)
        response = self.client.get(
            '/protected',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']

        # Test rate limiting
        test_token = self._jwt_handler.generate_token({'sub': 'rate_limit_test'})
        for _ in range(RATE_LIMIT_CONSTANTS['REQUESTS_PER_HOUR'] + 1):
            response = self.client.get(
                '/protected',
                headers={'Authorization': f'Bearer {test_token}'}
            )
        assert response.status_code == HTTP_STATUS_CODES['RATE_LIMITED']