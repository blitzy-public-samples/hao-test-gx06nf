"""
Unit tests for SQLAlchemy models including User, Project, Specification and Item models.
Tests model validation, relationships, constraints and business rules.

Version: 1.0.0
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from db.models.users import User
from db.models.projects import Project
from db.models.specifications import Specification
from db.models.items import Item
from utils.constants import DATABASE_CONSTANTS

@pytest.mark.unit
class TestUserModel:
    """Test suite for User model validation and relationships."""

    def test_user_creation_valid(self, db_session):
        """Test creation of user with valid data."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        db_session.commit()

        assert user.google_id == "123456789012345678901"
        assert user.email == "test@example.com"
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.last_login, datetime)

    def test_user_invalid_email(self, db_session):
        """Test user creation with invalid email format."""
        with pytest.raises(ValueError, match="Invalid email format"):
            User(
                google_id="123456789012345678901",
                email="invalid-email"
            )

    def test_user_invalid_google_id(self, db_session):
        """Test user creation with invalid Google ID."""
        with pytest.raises(ValueError, match="google_id cannot be empty"):
            User(
                google_id="",
                email="test@example.com"
            )

    def test_user_email_unique_constraint(self, db_session):
        """Test email uniqueness constraint."""
        user1 = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user1)
        db_session.commit()

        user2 = User(
            google_id="223456789012345678901",
            email="test@example.com"
        )
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_user_project_cascade_delete(self, db_session):
        """Test cascade deletion of projects when user is deleted."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        db_session.commit()

        project = Project(
            title="Test Project",
            owner_id=user.google_id
        )
        db_session.add(project)
        db_session.commit()

        db_session.delete(user)
        db_session.commit()

        assert db_session.query(Project).count() == 0

    def test_user_last_login_update(self, db_session):
        """Test last_login timestamp update functionality."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        db_session.commit()

        original_login = user.last_login
        user.update_last_login()
        db_session.commit()

        assert user.last_login > original_login

@pytest.mark.unit
class TestProjectModel:
    """Test suite for Project model validation and relationships."""

    def test_project_creation_valid(self, db_session):
        """Test creation of project with valid data."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        db_session.commit()

        project = Project(
            title="Test Project",
            owner_id=user.google_id
        )
        db_session.add(project)
        db_session.commit()

        assert project.title == "Test Project"
        assert project.owner_id == user.google_id
        assert isinstance(project.created_at, datetime)
        assert isinstance(project.updated_at, datetime)

    def test_project_title_length_validation(self, db_session):
        """Test project title length validation."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        db_session.commit()

        with pytest.raises(ValueError, match="Project title cannot exceed"):
            Project(
                title="a" * (DATABASE_CONSTANTS['MAX_TITLE_LENGTH'] + 1),
                owner_id=user.google_id
            )

    def test_project_title_sanitization(self, db_session):
        """Test project title sanitization."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        db_session.commit()

        project = Project(
            title="  Test Project  ",
            owner_id=user.google_id
        )
        db_session.add(project)
        db_session.commit()

        assert project.title == "Test Project"

    def test_project_specification_cascade_delete(self, db_session):
        """Test cascade deletion of specifications when project is deleted."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        db_session.commit()

        project = Project(
            title="Test Project",
            owner_id=user.google_id
        )
        db_session.add(project)
        db_session.commit()

        spec = Specification(
            project_id=project.project_id,
            content="Test Specification"
        )
        db_session.add(spec)
        db_session.commit()

        db_session.delete(project)
        db_session.commit()

        assert db_session.query(Specification).count() == 0

@pytest.mark.unit
class TestSpecificationModel:
    """Test suite for Specification model validation and relationships."""

    def test_specification_creation_valid(self, db_session):
        """Test creation of specification with valid data."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        project = Project(
            title="Test Project",
            owner_id=user.google_id
        )
        db_session.add(project)
        db_session.commit()

        spec = Specification(
            project_id=project.project_id,
            content="Test Specification",
            order_index=0
        )
        db_session.add(spec)
        db_session.commit()

        assert spec.content == "Test Specification"
        assert spec.order_index == 0
        assert isinstance(spec.created_at, datetime)

    def test_specification_content_validation(self, db_session):
        """Test specification content validation."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        project = Project(
            title="Test Project",
            owner_id=user.google_id
        )
        db_session.add(project)
        db_session.commit()

        with pytest.raises(ValueError, match="Content must be between"):
            Specification(
                project_id=project.project_id,
                content="a" * (DATABASE_CONSTANTS['MAX_CONTENT_LENGTH'] + 1)
            )

    def test_specification_max_limit(self, db_session):
        """Test maximum specifications per project limit."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        project = Project(
            title="Test Project",
            owner_id=user.google_id
        )
        db_session.add(project)
        db_session.commit()

        # Add maximum allowed specifications
        for i in range(DATABASE_CONSTANTS['MAX_SPECIFICATIONS_PER_PROJECT']):
            spec = Specification(
                project_id=project.project_id,
                content=f"Specification {i}",
                order_index=i
            )
            db_session.add(spec)
        db_session.commit()

        # Try to add one more
        spec = Specification(
            project_id=project.project_id,
            content="One too many",
            order_index=DATABASE_CONSTANTS['MAX_SPECIFICATIONS_PER_PROJECT']
        )
        db_session.add(spec)
        with pytest.raises(SQLAlchemyError, match="Maximum specifications per project limit"):
            db_session.commit()
        db_session.rollback()

@pytest.mark.unit
class TestItemModel:
    """Test suite for Item model validation and relationships."""

    def test_item_creation_valid(self, db_session):
        """Test creation of item with valid data."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        project = Project(
            title="Test Project",
            owner_id=user.google_id
        )
        db_session.add(project)
        spec = Specification(
            project_id=project.project_id,
            content="Test Specification"
        )
        db_session.add(spec)
        db_session.commit()

        item = Item(
            spec_id=spec.spec_id,
            content="Test Item",
            order_index=0
        )
        db_session.add(item)
        db_session.commit()

        assert item.content == "Test Item"
        assert item.order_index == 0
        assert isinstance(item.created_at, datetime)

    def test_item_max_limit(self, db_session):
        """Test maximum items per specification limit."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        project = Project(
            title="Test Project",
            owner_id=user.google_id
        )
        db_session.add(project)
        spec = Specification(
            project_id=project.project_id,
            content="Test Specification"
        )
        db_session.add(spec)
        db_session.commit()

        # Add maximum allowed items
        for i in range(DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']):
            item = Item(
                spec_id=spec.spec_id,
                content=f"Item {i}",
                order_index=i
            )
            db_session.add(item)
        db_session.commit()

        # Try to add one more
        item = Item(
            spec_id=spec.spec_id,
            content="One too many",
            order_index=DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']
        )
        db_session.add(item)
        with pytest.raises(ValueError, match="Maximum number of items"):
            db_session.commit()
        db_session.rollback()

    def test_item_order_validation(self, db_session):
        """Test item order index validation."""
        user = User(
            google_id="123456789012345678901",
            email="test@example.com"
        )
        db_session.add(user)
        project = Project(
            title="Test Project",
            owner_id=user.google_id
        )
        db_session.add(project)
        spec = Specification(
            project_id=project.project_id,
            content="Test Specification"
        )
        db_session.add(spec)
        db_session.commit()

        with pytest.raises(ValueError, match="Order index must be between"):
            Item(
                spec_id=spec.spec_id,
                content="Test Item",
                order_index=-1
            )