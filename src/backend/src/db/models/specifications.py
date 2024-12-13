"""
SQLAlchemy model definition for specifications table representing top-level specifications
within projects. Implements specification storage, ordering, and relationships with enhanced
validation and security features.

Version: 1.0.0
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, event
from sqlalchemy.orm import relationship, validates
from sqlalchemy.exc import SQLAlchemyError

from ..session import Base
from ...utils.validators import validate_content_length, validate_order_index
from ...utils.constants import DATABASE_CONSTANTS

class Specification(Base):
    """
    SQLAlchemy model representing a top-level specification within a project.
    Implements content validation, ordering, and relationship management with
    enhanced security features.
    """
    __tablename__ = 'specifications'
    
    # Primary key and relationships
    spec_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey('projects.project_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Core fields
    content = Column(
        String(DATABASE_CONSTANTS['MAX_CONTENT_LENGTH']),
        nullable=False
    )
    order_index = Column(
        Integer,
        nullable=False,
        default=0,
        index=True
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    project = relationship(
        "Project",
        back_populates="specifications",
        lazy="joined"
    )
    items = relationship(
        "Item",
        back_populates="specification",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="Item.order_index"
    )
    
    def __init__(
        self,
        project_id: int,
        content: str,
        order_index: int = 0
    ) -> None:
        """
        Creates a new Specification instance with validated content and proper UTC timestamp.
        
        Args:
            project_id: ID of the parent project
            content: Specification content text
            order_index: Optional ordering index (defaults to 0)
            
        Raises:
            ValueError: If any validation fails
            SQLAlchemyError: If database constraints are violated
        """
        self.project_id = self._validate_project_id(project_id)
        self.content = self.validate_content(content)
        self.order_index = self._validate_order_index(order_index)
        self.created_at = datetime.now(timezone.utc)
    
    @validates('content')
    def validate_content(self, content: str) -> str:
        """
        Validates and sanitizes specification content with enhanced security checks.
        
        Args:
            content: Raw content string to validate
            
        Returns:
            str: Sanitized and validated content string
            
        Raises:
            ValueError: If content validation fails
        """
        if not content:
            raise ValueError("Specification content cannot be empty")
            
        if not validate_content_length(content):
            raise ValueError(
                f"Content must be between 1 and {DATABASE_CONSTANTS['MAX_CONTENT_LENGTH']} characters"
            )
            
        return content.strip()
    
    def reorder(self, new_order_index: int) -> None:
        """
        Updates the order_index of the specification with bounds validation.
        
        Args:
            new_order_index: New ordering position for the specification
            
        Raises:
            ValueError: If order index is invalid
        """
        self.order_index = self._validate_order_index(new_order_index)
    
    def _validate_project_id(self, project_id: int) -> int:
        """
        Validates project ID ensuring it's a positive integer.
        
        Args:
            project_id: Project ID to validate
            
        Returns:
            int: Validated project ID
            
        Raises:
            ValueError: If project ID is invalid
        """
        try:
            project_id = int(project_id)
            if project_id <= 0:
                raise ValueError
            return project_id
        except (ValueError, TypeError):
            raise ValueError("Project ID must be a positive integer")
    
    def _validate_order_index(self, order_index: int) -> int:
        """
        Validates order index ensuring it's within acceptable bounds.
        
        Args:
            order_index: Order index to validate
            
        Returns:
            int: Validated order index
            
        Raises:
            ValueError: If order index is invalid
        """
        if not validate_order_index(order_index):
            raise ValueError(
                f"Order index must be between {DATABASE_CONSTANTS['MIN_ORDER_INDEX']} "
                f"and {DATABASE_CONSTANTS['MAX_ORDER_INDEX']}"
            )
        return order_index
    
    def __repr__(self) -> str:
        """Returns string representation of the specification."""
        return f"<Specification(spec_id={self.spec_id}, project_id={self.project_id})>"

@event.listens_for(Specification, 'before_insert')
def check_specification_limit(mapper, connection, target):
    """
    Enforces maximum specifications per project limit before insert.
    
    Args:
        mapper: SQLAlchemy mapper
        connection: Active database connection
        target: Specification instance being inserted
        
    Raises:
        SQLAlchemyError: If specification limit is exceeded
    """
    spec_count = connection.scalar(
        f"SELECT COUNT(*) FROM specifications WHERE project_id = {target.project_id}"
    )
    
    if spec_count >= DATABASE_CONSTANTS['MAX_SPECIFICATIONS_PER_PROJECT']:
        raise SQLAlchemyError(
            f"Maximum specifications per project limit "
            f"({DATABASE_CONSTANTS['MAX_SPECIFICATIONS_PER_PROJECT']}) exceeded"
        )