"""
Service layer implementation for managing second-level items within specifications.
Provides comprehensive business logic for secure item creation, retrieval, ordering,
and deletion while enforcing validation rules and item count limitations.

Version: 1.0.0
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime

from db.repositories.items import ItemRepository
from api.schemas.items import ItemCreate, ItemUpdate
from utils.constants import (
    DATABASE_CONSTANTS,
    CACHE_CONSTANTS,
    ERROR_MESSAGES
)

# Configure logging
logger = logging.getLogger(__name__)

class ItemService:
    """
    Service class implementing comprehensive business logic for secure item management
    within specifications, including validation, ordering, and count limitations.
    """

    def __init__(self, repository: ItemRepository) -> None:
        """
        Initialize the item service with repository dependency injection.

        Args:
            repository: ItemRepository instance for database operations
        """
        self._repository = repository
        self._cache_ttl = CACHE_CONSTANTS['ITEMS_CACHE_TTL']
        logger.info("Initialized ItemService with repository")

    async def get_items_by_specification(self, spec_id: int) -> List[Dict]:
        """
        Securely retrieve all items for a specification with optimized caching.

        Args:
            spec_id: ID of the specification to get items for

        Returns:
            List[Dict]: List of items ordered by order_index

        Raises:
            ValueError: If specification ID is invalid
        """
        try:
            if not isinstance(spec_id, int) or spec_id <= 0:
                raise ValueError("Invalid specification ID")

            # Get items from repository
            items = self._repository.get_by_specification(spec_id)

            # Transform to response format
            response_items = [
                {
                    "item_id": item.item_id,
                    "content": item.content,
                    "order_index": item.order_index,
                    "created_at": item.created_at.isoformat()
                }
                for item in items
            ]

            logger.debug(
                "Retrieved items for specification",
                extra={
                    "spec_id": spec_id,
                    "item_count": len(response_items)
                }
            )

            return response_items

        except Exception as e:
            logger.error(
                "Error retrieving items",
                extra={
                    "spec_id": spec_id,
                    "error": str(e)
                }
            )
            raise

    async def create_item(self, item_data: ItemCreate) -> Dict:
        """
        Create a new item with comprehensive validation and security checks.

        Args:
            item_data: Validated item creation data

        Returns:
            Dict: Created item data

        Raises:
            ValueError: If validation fails or item limit is exceeded
        """
        try:
            # Check item count limit
            current_items = self._repository.get_by_specification(item_data.spec_id)
            if len(current_items) >= DATABASE_CONSTANTS['MAX_ITEMS_PER_SPECIFICATION']:
                raise ValueError(ERROR_MESSAGES['MAX_ITEMS_REACHED'])

            # Prepare item data
            item_dict = {
                "spec_id": item_data.spec_id,
                "content": item_data.content,
                "order_index": item_data.order_index
            }

            # Create item
            created_item = self._repository.create_item(item_dict)

            response_data = {
                "item_id": created_item.item_id,
                "content": created_item.content,
                "order_index": created_item.order_index,
                "created_at": created_item.created_at.isoformat()
            }

            logger.info(
                "Created new item",
                extra={
                    "spec_id": item_data.spec_id,
                    "item_id": created_item.item_id
                }
            )

            return response_data

        except Exception as e:
            logger.error(
                "Error creating item",
                extra={
                    "spec_id": item_data.spec_id,
                    "error": str(e)
                }
            )
            raise

    async def update_item(self, item_id: int, item_data: ItemUpdate) -> Dict:
        """
        Update item with partial update support and validation.

        Args:
            item_id: ID of the item to update
            item_data: Validated update data

        Returns:
            Dict: Updated item data

        Raises:
            ValueError: If item not found or validation fails
        """
        try:
            # Get existing item
            existing_item = self._repository.get_by_id(item_id)
            if not existing_item:
                raise ValueError("Item not found")

            # Prepare update data
            update_dict = {}
            if item_data.content is not None:
                update_dict["content"] = item_data.content
            if item_data.order_index is not None:
                update_dict["order_index"] = item_data.order_index

            # Update item
            updated_item = self._repository.update(item_id, update_dict)

            response_data = {
                "item_id": updated_item.item_id,
                "content": updated_item.content,
                "order_index": updated_item.order_index,
                "created_at": updated_item.created_at.isoformat()
            }

            logger.info(
                "Updated item",
                extra={
                    "item_id": item_id,
                    "updated_fields": list(update_dict.keys())
                }
            )

            return response_data

        except Exception as e:
            logger.error(
                "Error updating item",
                extra={
                    "item_id": item_id,
                    "error": str(e)
                }
            )
            raise

    async def delete_item(self, item_id: int) -> bool:
        """
        Delete item with automatic reordering of remaining items.

        Args:
            item_id: ID of the item to delete

        Returns:
            bool: True if deletion successful

        Raises:
            ValueError: If item not found
        """
        try:
            # Delete item and reorder
            result = self._repository.delete_item(item_id)

            logger.info(
                "Deleted item",
                extra={"item_id": item_id}
            )

            return result

        except Exception as e:
            logger.error(
                "Error deleting item",
                extra={
                    "item_id": item_id,
                    "error": str(e)
                }
            )
            raise

    async def reorder_items(self, spec_id: int, order_updates: List[Dict]) -> List[Dict]:
        """
        Batch update item ordering with optimized transaction handling.

        Args:
            spec_id: ID of the specification containing the items
            order_updates: List of dictionaries with item_id and new order_index

        Returns:
            List[Dict]: List of updated items with new ordering

        Raises:
            ValueError: If validation fails
        """
        try:
            # Validate order updates format
            if not isinstance(order_updates, list):
                raise ValueError("Invalid order updates format")

            for update in order_updates:
                if not isinstance(update, dict) or \
                   'item_id' not in update or \
                   'order_index' not in update:
                    raise ValueError("Invalid order update entry format")

            # Update orders
            updated_items = self._repository.update_order(spec_id, order_updates)

            # Transform to response format
            response_items = [
                {
                    "item_id": item.item_id,
                    "content": item.content,
                    "order_index": item.order_index,
                    "created_at": item.created_at.isoformat()
                }
                for item in updated_items
            ]

            logger.info(
                "Reordered items",
                extra={
                    "spec_id": spec_id,
                    "updated_count": len(order_updates)
                }
            )

            return response_items

        except Exception as e:
            logger.error(
                "Error reordering items",
                extra={
                    "spec_id": spec_id,
                    "error": str(e)
                }
            )
            raise