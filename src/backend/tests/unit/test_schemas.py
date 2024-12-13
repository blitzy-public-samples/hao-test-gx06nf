"""
Unit tests for Pydantic schema validation and serialization.
Tests comprehensive validation rules, security patterns, and data integrity
for users, projects, specifications and items.

Version: 1.0.0
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from api.schemas.users import UserBase, UserCreate
from api.schemas.projects import ProjectBase
from api.schemas.specifications import SpecificationBase
from api.schemas.items import ItemBase
from utils.validators import (
    validate_content_length,
    validate_order_index,
    MAX_ITEMS_PER_SPECIFICATION
)

class TestUserSchemas:
    """Test suite for user-related Pydantic schemas."""

    @pytest.mark.unit
    def test_valid_user_base(self):
        """Tests valid user base schema creation."""
        # Test valid email format
        valid_user = UserBase(email="test@example.com")
        assert valid_user.email == "test@example.com"

        # Test email normalization
        mixed_case = UserBase(email="Test.User@Example.COM")
        assert mixed_case.email == "test.user@example.com"

    @pytest.mark.unit
    def test_invalid_user_base(self):
        """Tests invalid user base schema creation."""
        invalid_emails = [
            "",  # Empty email
            "invalid.email",  # Missing domain
            "user@.com",  # Invalid domain format
            "user@domain",  # Missing TLD
            f"{'a' * 256}@example.com",  # Too long
            "<script>alert(1)</script>@evil.com",  # XSS attempt
            "user@domain.com'--",  # SQL injection attempt
        ]

        for email in invalid_emails:
            with pytest.raises(ValidationError) as exc_info:
                UserBase(email=email)
            assert "email" in str(exc_info.value)

    @pytest.mark.unit
    def test_valid_user_create(self):
        """Tests valid user creation schema."""
        valid_data = {
            "google_id": "123456789012345678901",
            "email": "user@example.com"
        }
        user = UserCreate(**valid_data)
        assert user.google_id == valid_data["google_id"]
        assert user.email == valid_data["email"]

    @pytest.mark.unit
    def test_invalid_user_create(self):
        """Tests invalid user creation schema."""
        invalid_data = [
            {
                "google_id": "12345",  # Too short
                "email": "user@example.com"
            },
            {
                "google_id": "12345678901234567890123",  # Too long
                "email": "user@example.com"
            },
            {
                "google_id": "abcdefghijk12345678901",  # Invalid format
                "email": "user@example.com"
            }
        ]

        for data in invalid_data:
            with pytest.raises(ValidationError) as exc_info:
                UserCreate(**data)
            assert "google_id" in str(exc_info.value)

class TestProjectSchemas:
    """Test suite for project-related Pydantic schemas."""

    @pytest.mark.unit
    def test_valid_project_base(self):
        """Tests valid project base schema creation."""
        # Test valid title
        valid_project = ProjectBase(title="Test Project")
        assert valid_project.title == "Test Project"

        # Test title trimming
        whitespace_project = ProjectBase(title="  Padded Title  ")
        assert whitespace_project.title == "Padded Title"

    @pytest.mark.unit
    def test_invalid_project_base(self):
        """Tests invalid project base schema creation."""
        invalid_titles = [
            "",  # Empty title
            "  ",  # Only whitespace
            "<script>alert(1)</script>",  # XSS attempt
            "Title'; DROP TABLE projects;--",  # SQL injection attempt
            "a" * 256,  # Exceeds max length
        ]

        for title in invalid_titles:
            with pytest.raises(ValidationError) as exc_info:
                ProjectBase(title=title)
            assert "title" in str(exc_info.value)

class TestSpecificationSchemas:
    """Test suite for specification-related Pydantic schemas."""

    @pytest.mark.unit
    def test_valid_specification_base(self):
        """Tests valid specification base schema creation."""
        valid_data = {
            "content": "Valid specification content",
            "order_index": 0
        }
        spec = SpecificationBase(**valid_data)
        assert spec.content == valid_data["content"]
        assert spec.order_index == valid_data["order_index"]

        # Test maximum valid order
        max_order = SpecificationBase(
            content="Test content",
            order_index=999999
        )
        assert max_order.order_index == 999999

    @pytest.mark.unit
    def test_invalid_specification_content(self):
        """Tests invalid specification content."""
        invalid_contents = [
            "",  # Empty content
            "a" * 1001,  # Exceeds max length
            "<script>alert(1)</script>",  # XSS attempt
            "Content'; DROP TABLE specs;--",  # SQL injection attempt
            "Content with invalid < > characters",  # Invalid characters
        ]

        for content in invalid_contents:
            with pytest.raises(ValidationError) as exc_info:
                SpecificationBase(content=content, order_index=0)
            assert "content" in str(exc_info.value)

    @pytest.mark.unit
    def test_invalid_specification_order(self):
        """Tests invalid specification ordering."""
        invalid_orders = [
            -1,  # Negative index
            1000000,  # Exceeds maximum
            "not_a_number",  # Invalid type
        ]

        for order in invalid_orders:
            with pytest.raises(ValidationError) as exc_info:
                SpecificationBase(
                    content="Valid content",
                    order_index=order
                )
            assert "order_index" in str(exc_info.value)

class TestItemSchemas:
    """Test suite for item-related Pydantic schemas."""

    @pytest.mark.unit
    def test_valid_item_base(self):
        """Tests valid item base schema creation."""
        valid_data = {
            "content": "Valid item content",
            "order_index": 0
        }
        item = ItemBase(**valid_data)
        assert item.content == valid_data["content"]
        assert item.order_index == valid_data["order_index"]

        # Test content with allowed special characters
        special_content = ItemBase(
            content="Content with allowed chars: .,!?-",
            order_index=0
        )
        assert special_content.content == "Content with allowed chars: .,!?-"

    @pytest.mark.unit
    def test_invalid_item_content(self):
        """Tests invalid item content."""
        invalid_contents = [
            "",  # Empty content
            "a" * 1001,  # Exceeds max length
            "<div>HTML content</div>",  # HTML attempt
            "Content'; SELECT * FROM items;--",  # SQL injection attempt
            "Content with & symbol",  # Invalid character
        ]

        for content in invalid_contents:
            with pytest.raises(ValidationError) as exc_info:
                ItemBase(content=content, order_index=0)
            assert "content" in str(exc_info.value)

    @pytest.mark.unit
    def test_items_count_validation(self):
        """Tests maximum items per specification validation."""
        # Test maximum items limit
        items = []
        for i in range(MAX_ITEMS_PER_SPECIFICATION):
            item = ItemBase(
                content=f"Item {i}",
                order_index=i
            )
            items.append(item)
        assert len(items) == MAX_ITEMS_PER_SPECIFICATION

        # Test exceeding limit
        with pytest.raises(ValidationError) as exc_info:
            ItemBase(
                content=f"Item {MAX_ITEMS_PER_SPECIFICATION + 1}",
                order_index=MAX_ITEMS_PER_SPECIFICATION
            )
        assert "maximum number of items" in str(exc_info.value).lower()