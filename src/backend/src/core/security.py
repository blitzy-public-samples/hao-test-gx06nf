"""
Core security module for the Specification Management API.

This module implements enterprise-grade security features including:
- AES-256-GCM encryption for sensitive data
- Secure password hashing with salting
- JWT token management with blacklisting
- Cryptographic operations using industry-standard algorithms

Version: 1.0
"""

import base64
from datetime import datetime
import jwt  # version 2.0+
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # version 3.4+
from cryptography.hazmat.primitives import hashes  # version 3.4+
from cryptography.exceptions import InvalidTag
import secrets  # version 3.8+
import hashlib  # version 3.8+
from typing import Tuple, Optional, Set

from config.security import SecurityConfig
from utils.constants import AUTH_CONSTANTS

# Global constants
HASH_ALGORITHM = 'sha256'
ENCRYPTION_ALGORITHM = 'AES-256-GCM'
TOKEN_BLACKLIST: Set[str] = set()

def generate_salt(length: int = 32) -> bytes:
    """
    Generate a cryptographically secure random salt for password hashing.
    
    Args:
        length (int): Length of the salt in bytes (default: 32)
        
    Returns:
        bytes: Cryptographically secure random salt
        
    Raises:
        ValueError: If length is not positive
    """
    if length <= 0:
        raise ValueError("Salt length must be positive")
    return secrets.token_bytes(length)

def hash_password(password: str, salt: bytes) -> bytes:
    """
    Securely hash a password using SHA-256 with salt.
    
    Args:
        password (str): Plain text password to hash
        salt (bytes): Random salt value
        
    Returns:
        bytes: Securely hashed password
        
    Raises:
        TypeError: If inputs are of incorrect type
    """
    if not isinstance(password, str) or not isinstance(salt, bytes):
        raise TypeError("Invalid input types")
    
    # Create hash with salt
    hasher = hashlib.sha256()
    hasher.update(salt)
    hasher.update(password.encode('utf-8'))
    return hasher.digest()

def verify_password(password: str, salt: bytes, hash_value: bytes) -> bool:
    """
    Verify a password against its hash in constant time.
    
    Args:
        password (str): Password to verify
        salt (bytes): Salt used in original hash
        hash_value (bytes): Stored hash to compare against
        
    Returns:
        bool: True if password matches, False otherwise
    """
    calculated_hash = hash_password(password, salt)
    return secrets.compare_digest(calculated_hash, hash_value)

class SecurityManager:
    """
    Core security manager handling encryption, token management and security operations.
    Implements AES-256-GCM encryption and JWT token management with blacklisting.
    """
    
    def __init__(self):
        """Initialize the security manager with required keys and configurations."""
        # Generate encryption key if not exists
        self._encryption_key = AESGCM.generate_key(bit_length=256)
        
        # Load JWT configuration
        self._jwt_secret = SecurityConfig.JWT_SECRET_KEY
        self._jwt_algorithm = SecurityConfig.JWT_ALGORITHM
        
        if not self._jwt_secret or not self._jwt_algorithm:
            raise ValueError("Missing required JWT configuration")

    def encrypt_data(self, data: bytes) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt data using AES-256-GCM with authentication.
        
        Args:
            data (bytes): Data to encrypt
            
        Returns:
            Tuple[bytes, bytes, bytes]: (encrypted_data, nonce, tag)
            
        Raises:
            ValueError: If data is empty
            TypeError: If data is not bytes
        """
        if not data:
            raise ValueError("Data cannot be empty")
        if not isinstance(data, bytes):
            raise TypeError("Data must be bytes")

        # Create AESGCM instance
        aesgcm = AESGCM(self._encryption_key)
        
        # Generate random 96-bit nonce
        nonce = secrets.token_bytes(12)
        
        # Encrypt data and get authentication tag
        encrypted_data = aesgcm.encrypt(nonce, data, None)
        
        # Split encrypted data and authentication tag
        tag = encrypted_data[-16:]
        encrypted_data = encrypted_data[:-16]
        
        return encrypted_data, nonce, tag

    def decrypt_data(self, encrypted_data: bytes, nonce: bytes, tag: bytes) -> bytes:
        """
        Decrypt data using AES-256-GCM with authentication verification.
        
        Args:
            encrypted_data (bytes): Encrypted data
            nonce (bytes): Nonce used in encryption
            tag (bytes): Authentication tag
            
        Returns:
            bytes: Decrypted data
            
        Raises:
            InvalidTag: If authentication fails
            ValueError: If inputs are invalid
        """
        if not all([encrypted_data, nonce, tag]):
            raise ValueError("Missing required decryption parameters")
            
        # Recreate AESGCM instance
        aesgcm = AESGCM(self._encryption_key)
        
        try:
            # Combine encrypted data and tag
            ciphertext_and_tag = encrypted_data + tag
            
            # Decrypt and verify
            return aesgcm.decrypt(nonce, ciphertext_and_tag, None)
        except InvalidTag:
            raise InvalidTag("Authentication failed - data may be corrupted")

    def create_token(self, user_id: str, expiry: datetime) -> str:
        """
        Create a JWT token for a user.
        
        Args:
            user_id (str): User identifier
            expiry (datetime): Token expiration time
            
        Returns:
            str: Signed JWT token
            
        Raises:
            ValueError: If parameters are invalid
        """
        if not user_id or not expiry:
            raise ValueError("Missing required token parameters")
            
        payload = {
            'sub': user_id,
            'exp': expiry.timestamp(),
            'iat': datetime.utcnow().timestamp(),
            'type': 'access'
        }
        
        return jwt.encode(
            payload,
            self._jwt_secret,
            algorithm=self._jwt_algorithm
        )

    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify and decode a JWT token.
        
        Args:
            token (str): JWT token to verify
            
        Returns:
            Optional[dict]: Decoded token payload if valid, None otherwise
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        if not token or token in TOKEN_BLACKLIST:
            return None
            
        try:
            payload = jwt.decode(
                token,
                self._jwt_secret,
                algorithms=[self._jwt_algorithm]
            )
            return payload if payload.get('exp') > datetime.utcnow().timestamp() else None
        except jwt.InvalidTokenError:
            return None

    def blacklist_token(self, token: str) -> bool:
        """
        Add a token to the blacklist.
        
        Args:
            token (str): Token to blacklist
            
        Returns:
            bool: True if blacklisting successful
        """
        if not token or not self.verify_token(token):
            return False
            
        TOKEN_BLACKLIST.add(token)
        return True

    def is_token_blacklisted(self, token: str) -> bool:
        """
        Check if a token is blacklisted.
        
        Args:
            token (str): Token to check
            
        Returns:
            bool: True if token is blacklisted
        """
        return token in TOKEN_BLACKLIST

    @staticmethod
    def clean_blacklist() -> None:
        """Remove expired tokens from blacklist."""
        current_time = datetime.utcnow().timestamp()
        TOKEN_BLACKLIST.difference_update(
            token for token in TOKEN_BLACKLIST
            if jwt.decode(token, options={"verify_signature": False}).get('exp', 0) < current_time
        )