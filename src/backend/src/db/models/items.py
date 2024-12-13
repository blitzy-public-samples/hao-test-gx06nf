"""
SQLAlchemy model definition for items table representing second-level entries within specifications.
Implements item hierarchy with ordering capabilities and enforces a maximum limit of 10 items per specification.

Version: 1.0.0
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, event
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import select

from ..session import Base
from ...utils.validators import validate_order_index, validate_content_length
from ...utils.constants import DATABASE_CONSTANTS, ERROR_MESSAGES

class Item(Base):
    """
    SQLAlchemy model representing a second-level item entry belonging to a specification.
    Enforces a maximum limit of 10 items per specification with content validation and ordering.
    """
    __tablename__ = 'items'

    # Primary key
    item_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to specifications table
    spec_id = Column(
        Integer, 
        ForeignKey('specifications.spec_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Item content with length validation
    content = Column(
        String(DATABASE_CONSTANTS['MAX_CONTENT_LENGTH']),
        nullable=False
    )
    
    # Order index for maintaining item sequence
    order_index = Column(
        Integer,
        nullable=False,
        index=True
    )
    
    # Timestamp for item creation
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    # Relationship to parent specification
    specification = relationship(
        "Specification",
        back_populates="items",
        lazy="joined"
    )

    def __init__(self, spec_id: int, content: str, order_index: int):
        """
        Initialize a new Item instance with validation.

        Args:
            spec_id: ID of the parent specification
            content: Item content text
            order_index: Position in the item sequence

        Raises:
            ValueError: If any input validation fails
        """
        self.spec_id = spec_id
        self.content = content  # Will be validated by validate_content
        self.order_index = order_index  # Will be validated by validate_order
        self.created_at = datetime.utcnow()

    @validates('content')
    def validate_content(self, key: str, content: Optional[str]) -> str:
        """
        Validates and sanitizes item content.

        Args:
            key: Field name being validated
            content: Content string to validate

        Returns:
            str: Validated and sanitized content

        Raises:
            ValueError: If content validation fails
        """
        if not content or not validate_content_length(content):
            raise ValueError(
                f"Content must be between 1 and {DATABASE_CONSTANTS['MAX_CONTENT_LENGTH']} characters"
            )
        return content.strip()

    @validates('order_index')
    def validate_order(self, key: str, order_index: Optional[int]) -> int:
        """
        Validates item order index.

        Args:
            key: Field name being validated
            order_index: Order index to validate

        Returns:
            int: Validated order index

        Raises:
            ValueError: If order index validation fails
        """
        if not validate_order_index(order_index):
            raise ValueError(ERROR_MESSAGES['INVALID_ORDER_INDEX'])
        return order_index

    def __repr__(self) -> str:
        """String representation of the Item model."""
        return f"<Item(item_id={self.item_id}, spec_id={self.spec_id}, order_index={self.order_index})>"

@event.listens_for(Item, 'before_insert')
def validate_item_count(mapper, connection, target) -> bool:
    """
    Validates that a specification does not exceed the maximum allowed items (10).
    Triggered before item insertion.

    Args:
        mapper: SQLAlchemy mapper
        connection: Active database connection
        target: Item instance being inserted

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If item limit is exceeded
    """
    # Query current item count for the specification
    current_count = connection.scalar(
        select([func.count()]).where(Item.spec_id == target.spec_id)
    )

    # Check against maximum limit
    if current_count >= DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']:
        raise ValueError(ERROR_MESSAGES['MAX_ITEMS_REACHED'])
    
    return True

# Import func here to avoid circular imports
from sqlalchemy.sql.functions import func