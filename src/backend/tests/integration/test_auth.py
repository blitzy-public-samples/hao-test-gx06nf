"""
Integration tests for authentication functionality including Google OAuth flow,
JWT token management, rate limiting, and security controls.

Version: 1.0
"""

import pytest
from datetime import datetime, timedelta
import json
from unittest.mock import patch, Mock
from freezegun import freeze_time
import fakeredis

from api.auth.google import GoogleAuthClient
from api.auth.jwt import JWTHandler
from api.auth.utils import extract_token, is_token_blacklisted
from config.security import SecurityConfig
from utils.constants import AUTH_CONSTANTS, ERROR_MESSAGES, HTTP_STATUS_CODES

class MockGoogleResponses:
    """Mock response fixtures for Google OAuth endpoints with various test scenarios."""

    def __init__(self):
        """Initialize comprehensive mock response data for different test scenarios."""
        self.valid_token_response = {
            'iss': 'https://accounts.google.com',
            'sub': 'test_user_123',
            'email': 'test@example.com',
            'email_verified': True,
            'aud': SecurityConfig.JWT_SECRET_KEY,
            'exp': int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            'iat': int(datetime.utcnow().timestamp())
        }

        self.valid_profile_response = {
            'sub': 'test_user_123',
            'email': 'test@example.com',
            'email_verified': True,
            'name': 'Test User',
            'picture': 'https://example.com/picture.jpg'
        }

        self.invalid_token_response = {
            'error': 'invalid_token',
            'error_description': 'Invalid token format'
        }

        self.expired_token_response = {
            **self.valid_token_response,
            'exp': int((datetime.utcnow() - timedelta(hours=1)).timestamp())
        }

        self.malformed_token_response = {
            'error': 'invalid_token',
            'error_description': 'Malformed token'
        }

    def get_mock_token_info(self, scenario: str) -> dict:
        """Get mock token verification response for different scenarios."""
        scenarios = {
            'valid': self.valid_token_response,
            'invalid': self.invalid_token_response,
            'expired': self.expired_token_response,
            'malformed': self.malformed_token_response
        }
        return scenarios.get(scenario, self.invalid_token_response)


@pytest.mark.integration
async def test_google_auth_success(test_client, db_session, redis_client):
    """Test successful Google OAuth authentication flow with comprehensive validation."""
    mock_responses = MockGoogleResponses()
    mock_token = "valid_google_token"

    # Mock Google OAuth token verification
    with patch('api.auth.google.GoogleAuthClient.verify_oauth_token') as mock_verify:
        mock_verify.return_value = mock_responses.valid_token_response

        # Mock Google profile retrieval
        with patch('api.auth.google.GoogleAuthClient.get_user_profile') as mock_profile:
            mock_profile.return_value = mock_responses.valid_profile_response

            # Send authentication request
            response = await test_client.post(
                '/api/v1/auth/login',
                json={'token': mock_token}
            )

            # Verify response status and structure
            assert response.status_code == HTTP_STATUS_CODES['OK']
            data = json.loads(response.data)
            assert 'access_token' in data
            assert 'token_type' in data
            assert data['token_type'] == AUTH_CONSTANTS['BEARER_TOKEN_PREFIX']

            # Validate JWT token
            jwt_handler = JWTHandler()
            token_payload = jwt_handler.validate_token(data['access_token'])
            assert token_payload['sub'] == mock_responses.valid_token_response['sub']
            assert token_payload['email'] == mock_responses.valid_token_response['email']

            # Verify user creation in database
            user = await db_session.execute(
                "SELECT * FROM users WHERE google_id = :google_id",
                {'google_id': mock_responses.valid_token_response['sub']}
            )
            user_data = user.fetchone()
            assert user_data is not None
            assert user_data.email == mock_responses.valid_token_response['email']

            # Check Redis cache entries
            assert await redis_client.exists(f"user:{user_data.google_id}")
            
            # Validate security headers
            assert response.headers.get('X-Frame-Options') == 'DENY'
            assert response.headers.get('X-Content-Type-Options') == 'nosniff'
            assert response.headers.get('X-XSS-Protection') == '1; mode=block'


@pytest.mark.integration
async def test_google_auth_invalid_token(test_client, redis_client):
    """Test authentication failures with various invalid token scenarios."""
    mock_responses = MockGoogleResponses()

    # Test expired token
    with patch('api.auth.google.GoogleAuthClient.verify_oauth_token') as mock_verify:
        mock_verify.return_value = mock_responses.expired_token_response
        response = await test_client.post(
            '/api/v1/auth/login',
            json={'token': 'expired_token'}
        )
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']
        assert ERROR_MESSAGES['INVALID_TOKEN'] in response.data.decode()

    # Test malformed token
    with patch('api.auth.google.GoogleAuthClient.verify_oauth_token') as mock_verify:
        mock_verify.side_effect = ValueError("Malformed token")
        response = await test_client.post(
            '/api/v1/auth/login',
            json={'token': 'malformed_token'}
        )
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']

    # Test revoked token
    with patch('api.auth.utils.is_token_blacklisted') as mock_blacklist:
        mock_blacklist.return_value = True
        response = await test_client.post(
            '/api/v1/auth/login',
            json={'token': 'revoked_token'}
        )
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']


@pytest.mark.integration
async def test_rate_limiting(test_client, redis_client):
    """Test login attempt rate limiting and lockout functionality."""
    mock_responses = MockGoogleResponses()
    test_ip = '127.0.0.1'

    # Attempt multiple failed logins
    for _ in range(SecurityConfig.MAX_LOGIN_ATTEMPTS):
        with patch('api.auth.google.GoogleAuthClient.verify_oauth_token') as mock_verify:
            mock_verify.side_effect = ValueError("Invalid token")
            response = await test_client.post(
                '/api/v1/auth/login',
                json={'token': 'invalid_token'},
                headers={'X-Real-IP': test_ip}
            )
            assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']

    # Verify rate limit lockout
    response = await test_client.post(
        '/api/v1/auth/login',
        json={'token': 'valid_token'},
        headers={'X-Real-IP': test_ip}
    )
    assert response.status_code == HTTP_STATUS_CODES['RATE_LIMITED']
    assert ERROR_MESSAGES['AUTH_LOCKOUT'] in response.data.decode()

    # Verify lockout duration
    with freeze_time(datetime.utcnow() + timedelta(minutes=SecurityConfig.LOGIN_ATTEMPT_LOCKOUT_MINUTES - 1)):
        response = await test_client.post(
            '/api/v1/auth/login',
            json={'token': 'valid_token'},
            headers={'X-Real-IP': test_ip}
        )
        assert response.status_code == HTTP_STATUS_CODES['RATE_LIMITED']


@pytest.mark.integration
async def test_jwt_token_lifecycle(test_client, auth_headers, redis_client):
    """Test complete JWT token lifecycle including refresh and revocation."""
    jwt_handler = JWTHandler()
    
    # Generate test token
    test_payload = {
        'sub': 'test_user_123',
        'email': 'test@example.com'
    }
    token = jwt_handler.generate_token(test_payload)

    # Verify token validation
    payload = jwt_handler.validate_token(token)
    assert payload['sub'] == test_payload['sub']
    assert payload['email'] == test_payload['email']

    # Test token refresh
    response = await test_client.post(
        '/api/v1/auth/refresh',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == HTTP_STATUS_CODES['OK']
    new_token = json.loads(response.data)['access_token']
    assert new_token != token

    # Test token revocation
    response = await test_client.post(
        '/api/v1/auth/logout',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == HTTP_STATUS_CODES['NO_CONTENT']
    assert await is_token_blacklisted(token)

    # Verify revoked token rejection
    response = await test_client.get(
        '/api/v1/projects',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']


@pytest.mark.integration
@freeze_time("2024-01-20 12:00:00")
async def test_token_expiration(test_client, auth_headers, redis_client):
    """Test JWT token expiration handling and refresh mechanics."""
    jwt_handler = JWTHandler()
    
    # Generate token with 24-hour expiration
    test_payload = {
        'sub': 'test_user_123',
        'email': 'test@example.com'
    }
    token = jwt_handler.generate_token(test_payload)

    # Test valid token
    response = await test_client.get(
        '/api/v1/projects',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == HTTP_STATUS_CODES['OK']

    # Test near expiration (23 hours later)
    with freeze_time(datetime.utcnow() + timedelta(hours=23)):
        response = await test_client.get(
            '/api/v1/projects',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == HTTP_STATUS_CODES['OK']

    # Test expired token (25 hours later)
    with freeze_time(datetime.utcnow() + timedelta(hours=25)):
        response = await test_client.get(
            '/api/v1/projects',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert response.status_code == HTTP_STATUS_CODES['UNAUTHORIZED']