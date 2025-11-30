"""
Tag-related data models.

This module contains Pydantic models for paper tags and categorization.
"""

from typing import List
from pydantic import BaseModel, Field


class Tags(BaseModel):
    """Tag structure for paper categorization."""
    top: List[str] = Field(description="Top-level categories (e.g., 'llm', 'computer vision')")
    tags: List[str] = Field(description="Specific tags (e.g., 'transformer', 'attention')")

