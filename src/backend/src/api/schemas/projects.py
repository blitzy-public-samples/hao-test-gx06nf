"""
Pydantic schema definitions for project-related request and response models.
Implements comprehensive validation and serialization for project data with
strict type checking and enhanced error handling.

Version: 1.0
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, validator, constr

from ...utils.validators import validate_content_length
from ...db.models.projects import Project
from ...utils.constants import DATABASE_CONSTANTS

class ProjectBase(BaseModel):
    """
    Base Pydantic model for project data validation with enhanced error handling
    and strict type checking.
    """
    # Title with constrained string type for automatic length validation
    title: constr(
        min_length=1,
        max_length=DATABASE_CONSTANTS['MAX_TITLE_LENGTH'],
        strip_whitespace=True
    )

    @validator('title', pre=True)
    def validate_title(cls, title: str) -> str:
        """
        Validates project title format and length with enhanced error messages.

        Args:
            title: Project title to validate

        Returns:
            str: Validated and sanitized title

        Raises:
            ValueError: If title validation fails with specific error message
        """
        if not title:
            raise ValueError("Project title is required")

        # Remove leading/trailing whitespace
        title = str(title).strip()

        # Validate content length
        if not validate_content_length(title):
            raise ValueError(
                f"Project title must be between 1 and {DATABASE_CONSTANTS['MAX_TITLE_LENGTH']} characters"
            )

        # Check for invalid characters
        if any(char in title for char in '<>&;'):
            raise ValueError("Project title contains invalid characters")

        return title

    class Config:
        """Pydantic model configuration."""
        anystr_strip_whitespace = True
        min_anystr_length = 1
        max_anystr_length = DATABASE_CONSTANTS['MAX_TITLE_LENGTH']
        error_msg_templates = {
            'value_error.missing': 'This field is required',
            'value_error.any_str.max_length': f"Maximum length is {DATABASE_CONSTANTS['MAX_TITLE_LENGTH']} characters",
            'value_error.any_str.min_length': 'Field cannot be empty'
        }


class ProjectCreate(ProjectBase):
    """
    Schema for project creation requests inheriting validation from ProjectBase.
    Only requires title field as other fields are set automatically.
    """
    pass


class ProjectResponse(ProjectBase):
    """
    Schema for project response data with complete type annotations and enhanced
    ORM conversion. Includes all project fields with proper validation.
    """
    project_id: int
    owner_id: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, db_project: Project) -> 'ProjectResponse':
        """
        Creates ProjectResponse from Project ORM model with error handling.

        Args:
            db_project: Project ORM model instance

        Returns:
            ProjectResponse: Validated response schema instance

        Raises:
            ValueError: If ORM conversion fails with detailed error message
        """
        if not isinstance(db_project, Project):
            raise ValueError("Invalid Project ORM instance")

        return cls(
            project_id=db_project.project_id,
            title=db_project.title,
            owner_id=db_project.owner_id,
            created_at=db_project.created_at,
            updated_at=db_project.updated_at
        )

    class Config:
        """Pydantic model configuration for ORM mode."""
        orm_mode = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
        schema_extra = {
            "example": {
                "project_id": 1,
                "title": "Sample Project",
                "owner_id": "123456789012345678901",
                "created_at": "2024-01-20T12:00:00Z",
                "updated_at": "2024-01-20T12:00:00Z"
            }
        }