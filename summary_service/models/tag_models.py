"""
Tag-related data models.

This module contains dataclasses for paper tags and categorization.
"""

from typing import List
from dataclasses import dataclass


@dataclass
class Tags:
    """Tag structure for paper categorization."""
    top: List[str]      # Top-level categories (e.g., "llm", "computer vision")
    tags: List[str]     # Specific tags (e.g., "transformer", "attention")
