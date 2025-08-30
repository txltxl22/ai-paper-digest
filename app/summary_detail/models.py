"""
Summary detail models for individual paper viewing.
"""
from typing import Dict, List, Optional, Any


class SummaryData:
    """Summary data structure for individual papers."""
    
    def __init__(self, arxiv_id: str, content: str, tags: Dict[str, List[str]]):
        self.arxiv_id = arxiv_id
        self.content = content
        self.tags = tags
    
    def get_all_tags(self) -> List[str]:
        """Extract all tags from the summary data."""
        tags: List[str] = []
        if isinstance(self.tags, dict):
            raw = []
            if isinstance(self.tags.get("top"), list):
                raw.extend(self.tags.get("top") or [])
            if isinstance(self.tags.get("tags"), list):
                raw.extend(self.tags.get("tags") or [])
            tags = [str(t).strip().lower() for t in raw if str(t).strip()]
        return tags


class ServiceData:
    """Service data structure for paper metadata."""
    
    def __init__(self, source_type: str = "system", user_id: Optional[str] = None, 
                 original_url: Optional[str] = None):
        self.source_type = source_type
        self.user_id = user_id
        self.original_url = original_url
