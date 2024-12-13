"""
SQLAlchemy model definition for projects table that represents user-owned projects
containing specifications. Implements project ownership, metadata management and
relationships with users and specifications.

Version: 1.0
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship, validates, backref

from ..session import Base
from ...utils.validators import sanitize_string
from ...utils.constants import DATABASE_CONSTANTS

class Project(Base):
    """
    SQLAlchemy model representing a user-owned project that contains specifications.
    Implements robust data validation, ownership controls, and cascade behaviors.
    """
    __tablename__ = 'projects'

    # Primary key and core fields
    project_id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    title = Column(String(DATABASE_CONSTANTS['MAX_TITLE_LENGTH']), nullable=False, index=True)
    owner_id = Column(
        String(255), 
        ForeignKey('users.google_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    owner = relationship(
        'User',
        backref=backref(
            'projects',
            lazy='dynamic',
            cascade='all, delete-orphan',
            passive_deletes=True
        )
    )
    specifications = relationship(
        'Specification',
        backref=backref(
            'project',
            lazy='joined'
        ),
        lazy='dynamic',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='Specification.order_index'
    )

    def __init__(self, title: str, owner_id: str) -> None:
        """
        Creates a new Project instance with validated title and proper timestamp initialization.

        Args:
            title (str): Project title, must be non-empty and pass sanitization
            owner_id (str): Valid Google user ID that owns this project

        Raises:
            ValueError: If title is invalid or owner_id is None/empty
        """
        if not owner_id:
            raise ValueError("owner_id is required")

        self.owner_id = owner_id
        self.title = self.validate_title(title)
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    @validates('title')
    def validate_title(self, title: str) -> str:
        """
        Validates and sanitizes project title with length and content checks.

        Args:
            title (str): Project title to validate

        Returns:
            str: Sanitized and validated title

        Raises:
            ValueError: If title is invalid or too long/short
        """
        if not title:
            raise ValueError("Project title is required")

        sanitized_title = sanitize_string(title)
        if not sanitized_title:
            raise ValueError("Project title cannot be empty after sanitization")

        if len(sanitized_title) > DATABASE_CONSTANTS['MAX_TITLE_LENGTH']:
            raise ValueError(
                f"Project title cannot exceed {DATABASE_CONSTANTS['MAX_TITLE_LENGTH']} characters"
            )

        return sanitized_title

    def update_timestamp(self) -> None:
        """Updates the updated_at timestamp to current UTC time."""
        self.updated_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        """
        Returns string representation of Project for debugging.

        Returns:
            str: String representation with project_id, title, and owner_id
        """
        return (
            f"<Project(project_id={self.project_id}, "
            f"title='{self.title}', "
            f"owner_id='{self.owner_id}')>"
        )