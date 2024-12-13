"""
Repository implementation for managing Item model database operations.

This module provides specialized methods for handling second-level items within specifications
including ordering, validation, and enforcing the 10-item limit per specification with
optimized query patterns and caching strategies.

Version: 1.0.0
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import func, and_, select, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from db.repositories.base import BaseRepository
from db.models.items import Item
from utils.constants import (
    DATABASE_CONSTANTS,
    CACHE_CONSTANTS,
    ERROR_MESSAGES
)

# Configure logging
logger = logging.getLogger(__name__)

class ItemRepository(BaseRepository[Item]):
    """
    Repository class for managing Item model database operations with specialized methods
    for item ordering, validation, and optimized query patterns.
    """

    _model_class = Item

    def __init__(self) -> None:
        """Initialize the item repository with Item model and setup caching."""
        super().__init__(Item)
        self._cache_ttl = CACHE_CONSTANTS['ITEMS_CACHE_TTL']
        self._cache_prefix = f"{CACHE_CONSTANTS['CACHE_KEY_PREFIX']}_items"

    def get_by_specification(self, spec_id: int) -> List[Item]:
        """
        Retrieve all items for a specific specification in order with caching.

        Args:
            spec_id: ID of the specification to get items for

        Returns:
            List[Item]: List of items ordered by order_index

        Raises:
            SQLAlchemyError: If database operation fails
        """
        cache_key = f"{self._cache_prefix}_spec_{spec_id}"
        
        try:
            # Build optimized query with eager loading
            query = self._db.query(Item)\
                .filter(Item.spec_id == spec_id)\
                .order_by(Item.order_index)\
                .options(joinedload(Item.specification))
            
            items = query.all()
            
            logger.debug(
                "Retrieved items for specification",
                extra={
                    "spec_id": spec_id,
                    "item_count": len(items)
                }
            )
            
            return items

        except SQLAlchemyError as e:
            logger.error(
                "Error retrieving items for specification",
                extra={
                    "spec_id": spec_id,
                    "error": str(e)
                }
            )
            raise

    def create_item(self, item_data: Dict[str, Any]) -> Item:
        """
        Create a new item with validation of 10-item limit and order management.

        Args:
            item_data: Dictionary containing item data (spec_id, content, order_index)

        Returns:
            Item: Created item instance

        Raises:
            ValueError: If validation fails or item limit is exceeded
            SQLAlchemyError: If database operation fails
        """
        try:
            # Start transaction
            self._db.begin_nested()

            # Check current item count
            current_count = self._db.query(func.count(Item.item_id))\
                .filter(Item.spec_id == item_data['spec_id'])\
                .scalar()

            if current_count >= DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']:
                raise ValueError(ERROR_MESSAGES['MAX_ITEMS_REACHED'])

            # Calculate next order index if not provided
            if 'order_index' not in item_data:
                max_order = self._db.query(func.max(Item.order_index))\
                    .filter(Item.spec_id == item_data['spec_id'])\
                    .scalar() or -1
                item_data['order_index'] = max_order + 1

            # Create item
            item = super().create(item_data)
            
            # Commit transaction
            self._db.commit()

            logger.info(
                "Created new item",
                extra={
                    "spec_id": item.spec_id,
                    "item_id": item.item_id,
                    "order_index": item.order_index
                }
            )

            return item

        except SQLAlchemyError as e:
            self._db.rollback()
            logger.error(
                "Error creating item",
                extra={
                    "item_data": item_data,
                    "error": str(e)
                }
            )
            raise

    def update_order(self, spec_id: int, order_updates: List[Dict[str, int]]) -> List[Item]:
        """
        Update the order of items within a specification with transaction safety.

        Args:
            spec_id: ID of the specification containing the items
            order_updates: List of dictionaries with item_id and new order_index

        Returns:
            List[Item]: List of updated items

        Raises:
            ValueError: If validation fails
            SQLAlchemyError: If database operation fails
        """
        try:
            # Start transaction
            self._db.begin_nested()

            # Validate all items belong to specification
            item_ids = [update['item_id'] for update in order_updates]
            items = self._db.query(Item)\
                .filter(and_(
                    Item.spec_id == spec_id,
                    Item.item_id.in_(item_ids)
                ))\
                .all()

            if len(items) != len(order_updates):
                raise ValueError("Invalid item IDs in order update request")

            # Update order indexes
            for update in order_updates:
                self._db.query(Item)\
                    .filter(Item.item_id == update['item_id'])\
                    .update({"order_index": update['order_index']})

            # Commit transaction
            self._db.commit()

            # Retrieve updated items
            updated_items = self.get_by_specification(spec_id)

            logger.info(
                "Updated item order indexes",
                extra={
                    "spec_id": spec_id,
                    "updated_count": len(order_updates)
                }
            )

            return updated_items

        except SQLAlchemyError as e:
            self._db.rollback()
            logger.error(
                "Error updating item order",
                extra={
                    "spec_id": spec_id,
                    "error": str(e)
                }
            )
            raise

    def delete_item(self, item_id: int) -> bool:
        """
        Delete an item and reorder remaining items with cache management.

        Args:
            item_id: ID of the item to delete

        Returns:
            bool: True if successful

        Raises:
            ValueError: If item not found
            SQLAlchemyError: If database operation fails
        """
        try:
            # Start transaction
            self._db.begin_nested()

            # Get item with lock
            item = self._db.query(Item)\
                .filter(Item.item_id == item_id)\
                .with_for_update()\
                .first()

            if not item:
                raise ValueError("Item not found")

            spec_id = item.spec_id
            deleted_order = item.order_index

            # Delete item
            super().delete(item_id)

            # Reorder remaining items
            self._db.query(Item)\
                .filter(and_(
                    Item.spec_id == spec_id,
                    Item.order_index > deleted_order
                ))\
                .update(
                    {"order_index": Item.order_index - 1},
                    synchronize_session=False
                )

            # Commit transaction
            self._db.commit()

            logger.info(
                "Deleted item and reordered remaining items",
                extra={
                    "item_id": item_id,
                    "spec_id": spec_id
                }
            )

            return True

        except SQLAlchemyError as e:
            self._db.rollback()
            logger.error(
                "Error deleting item",
                extra={
                    "item_id": item_id,
                    "error": str(e)
                }
            )
            raise