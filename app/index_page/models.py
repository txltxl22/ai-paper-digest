"""
Index page models for entry metadata and filtering.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import math


class EntryMetadata:
    """Entry metadata structure."""
    
    def __init__(self, entry_id: str, updated: datetime, tags: List[str], 
                 top_tags: List[str], detail_tags: List[str], 
                 source_type: str = "system", user_id: Optional[str] = None,
                 original_url: Optional[str] = None):
        self.id = entry_id
        self.updated = updated
        self.tags = tags
        self.top_tags = top_tags
        self.detail_tags = detail_tags
        self.source_type = source_type
        self.user_id = user_id
        self.original_url = original_url
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "updated": self.updated,
            "tags": self.tags,
            "top_tags": self.top_tags,
            "detail_tags": self.detail_tags,
            "source_type": self.source_type,
            "user_id": self.user_id,
            "original_url": self.original_url
        }


class TagCloud:
    """Tag cloud data structure."""
    
    def __init__(self):
        self.tag_counts: Dict[str, int] = {}
        self.top_counts: Dict[str, int] = {}
    
    def add_entry(self, entry):
        """Add an entry to the tag cloud."""
        # Handle both EntryMetadata objects and dictionaries
        if hasattr(entry, 'detail_tags'):
            detail_tags = entry.detail_tags
            top_tags = entry.top_tags
        else:
            # Assume it's a dictionary
            detail_tags = entry.get('detail_tags', [])
            top_tags = entry.get('top_tags', [])
        
        for tag in detail_tags:
            self.tag_counts[tag] = self.tag_counts.get(tag, 0) + 1
        for tag in top_tags:
            self.top_counts[tag] = self.top_counts.get(tag, 0) + 1
    
    def get_tag_cloud(self, query: str = None) -> List[Dict[str, Any]]:
        """Get sorted tag cloud."""
        tags = self.tag_counts.items()
        if query:
            tags = [(k, v) for k, v in tags if query in k]
        
        return sorted(
            ({"name": k, "count": v} for k, v in tags),
            key=lambda item: (-item["count"], item["name"]),
        )
    
    def get_top_cloud(self) -> List[Dict[str, Any]]:
        """Get sorted top tag cloud."""
        return sorted(
            ({"name": k, "count": v} for k, v in self.top_counts.items()),
            key=lambda item: (-item["count"], item["name"]),
        )


class Pagination:
    """Pagination data structure."""
    
    def __init__(self, total_items: int, page: int = 1, per_page: int = 10):
        self.total_items = total_items
        self.page = max(1, page)
        self.per_page = max(1, min(per_page, 100))
        self.total_pages = max(1, math.ceil(total_items / per_page))
        
        if self.page > self.total_pages:
            self.page = self.total_pages
        
        self.start = (self.page - 1) * self.per_page
        self.end = self.start + self.per_page
    
    def get_page_items(self, items: List[Any]) -> List[Any]:
        """Get items for current page."""
        return items[self.start:self.end]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page": self.page,
            "per_page": self.per_page,
            "total_pages": self.total_pages,
            "total_items": self.total_items
        }
