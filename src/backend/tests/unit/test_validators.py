"""
Unit tests for validation utility functions ensuring secure data validation,
schema compliance, and hierarchy constraints.

This test suite provides comprehensive coverage of validation logic including
security cases, edge conditions, and type safety.

Version: 1.0.0
"""

import pytest
from typing import Any, Union

from utils.validators import (
    validate_email,
    validate_content_length,
    validate_order_index,
    validate_items_count,
    validate_google_id,
    MAX_ITEMS_PER_SPECIFICATION,
    MAX_CONTENT_LENGTH,
    MIN_CONTENT_LENGTH
)

@pytest.mark.parametrize('email,expected', [
    # Valid email cases
    ('user@example.com', True),
    ('user.name@example.com', True),
    ('user+tag@example.com', True),
    ('user@subdomain.example.com', True),
    ('user@example.co.uk', True),
    ('123@example.com', True),
    ('user@123.com', True),
    ('USER@EXAMPLE.COM', True),
    
    # Invalid email cases
    ('', False),
    (None, False),
    ('invalid', False),
    ('@example.com', False),
    ('user@', False),
    ('user@.com', False),
    ('user@example.', False),
    ('user@exam ple.com', False),
    
    # Security test cases
    ('<script>@example.com', False),
    ('user@example.com<script>', False),
    ("user'--@example.com", True),  # SQL injection attempt but valid email
    ('user@example.com;drop table users;', False),
    
    # Length and boundary cases
    ('a' * 64 + '@' + 'b' * 63 + '.com', True),
    ('a' * 256 + '@example.com', False),
    ('a@b.c', True),  # Minimum valid length
    
    # Type safety cases
    (123, False),
    (12.34, False),
    ([], False),
    ({}, False)
])
def test_validate_email(email: Any, expected: bool) -> None:
    """
    Test email validation covering format compliance, security cases, and edge conditions.
    """
    assert validate_email(email) == expected

@pytest.mark.parametrize('content,expected', [
    # Valid content cases
    ('Valid content', True),
    ('a' * MIN_CONTENT_LENGTH, True),
    ('a' * MAX_CONTENT_LENGTH, True),
    ('Hello World!', True),
    ('Special chars: !@#$%^&*()', True),
    ('Numbers 123456789', True),
    ('Mixed Content 123 !@#', True),
    
    # Invalid content cases
    ('', False),
    (None, False),
    ('a' * (MAX_CONTENT_LENGTH + 1), False),
    (' ', False),  # Only whitespace
    
    # Security test cases
    ('<script>alert("xss")</script>', False),
    ('Content with <tags>', False),
    ('Content with &lt;escaped&gt;', False),
    ('Content;drop table users;', True),  # SQL injection attempt but valid content
    
    # Whitespace handling
    ('  Valid content  ', True),
    ('\tTabbed content\n', True),
    ('\n\n\n', False),
    
    # Type safety cases
    (123, False),
    (12.34, False),
    ([], False),
    ({}, False)
])
def test_validate_content_length(content: Any, expected: bool) -> None:
    """
    Test content length validation ensuring proper bounds and security.
    """
    assert validate_content_length(content) == expected

@pytest.mark.parametrize('order_index,expected', [
    # Valid order indices
    (0, True),
    (1, True),
    (100, True),
    (999999, True),
    ('42', True),  # String number
    
    # Invalid order indices
    (None, False),
    (-1, False),
    (1000001, False),
    ('invalid', False),
    ('', False),
    
    # Type safety cases
    (12.34, False),
    ('12.34', False),
    ([], False),
    ({}, False),
    (True, False),
    (False, False),
    
    # Boundary cases
    (1000000, True),
    ('0', True),
    ('-0', True)
])
def test_validate_order_index(order_index: Any, expected: bool) -> None:
    """
    Test order index validation including boundary and type cases.
    """
    assert validate_order_index(order_index) == expected

@pytest.mark.parametrize('count,expected', [
    # Valid counts
    (0, True),
    (1, True),
    (MAX_ITEMS_PER_SPECIFICATION - 1, True),
    ('5', True),  # String number
    
    # Invalid counts
    (None, False),
    (-1, False),
    (MAX_ITEMS_PER_SPECIFICATION, False),
    (MAX_ITEMS_PER_SPECIFICATION + 1, False),
    ('invalid', False),
    ('', False),
    
    # Type safety cases
    (12.34, False),
    ('12.34', False),
    ([], False),
    ({}, False),
    (True, False),
    (False, False),
    
    # Boundary cases
    (MAX_ITEMS_PER_SPECIFICATION - 1, True),
    ('0', True),
    ('-0', True)
])
def test_validate_items_count(count: Any, expected: bool) -> None:
    """
    Test items count validation ensuring specification limits.
    """
    assert validate_items_count(count) == expected

@pytest.mark.parametrize('google_id,expected', [
    # Valid Google IDs
    ('123456789012345678901', True),
    ('999999999999999999999', True),
    ('000000000000000000001', True),
    
    # Invalid Google IDs
    ('', False),
    (None, False),
    ('12345', False),
    ('1' * 20, False),  # Too short
    ('1' * 22, False),  # Too long
    ('abcdefghijklmnopqrstu', False),  # Letters
    ('12345678901234567890a', False),  # Mixed
    
    # Security test cases
    ('<script>12345678901', False),
    ('123456789012345678901;', False),
    ('12345678901234567890;', False),
    
    # Whitespace handling
    (' 123456789012345678901 ', True),
    ('\t123456789012345678901\n', True),
    
    # Type safety cases
    (123456789012345678901, False),
    (12.34, False),
    ([], False),
    ({}, False),
    (True, False)
])
def test_validate_google_id(google_id: Any, expected: bool) -> None:
    """
    Test Google ID validation covering format and security.
    """
    assert validate_google_id(google_id) == expected