"""
Summary detail models for individual paper viewing.
"""
from typing import Dict, List, Optional, Any
from summary_service.models import StructuredSummary, Tags


class SummaryData:
    """Summary data structure for individual papers."""
    
    def __init__(self, arxiv_id: str, content: str, tags: Dict[str, List[str]], 
                 structured_summary: Optional[StructuredSummary] = None):
        self.arxiv_id = arxiv_id
        self.content = content  # Markdown content for backward compatibility
        self.tags = tags
        self.structured_summary = structured_summary
    
    
    def get_top_tags(self) -> List[str]:
        """Extract top tags from the summary data."""
        tags: List[str] = []
        if isinstance(self.tags, dict):
            # Handle nested structure: {"tags": {"top": [...], "tags": [...]}}
            container = self.tags
            if isinstance(self.tags.get("tags"), dict):
                container = self.tags.get("tags") or {}
            
            if isinstance(container.get("top"), list):
                tags = [str(t).strip().lower() for t in container.get("top") if str(t).strip()]
        return tags
    
    def get_detail_tags(self) -> List[str]:
        """Extract detail tags from the summary data."""
        tags: List[str] = []
        if isinstance(self.tags, dict):
            # Handle nested structure: {"tags": {"top": [...], "tags": [...]}}
            container = self.tags
            if isinstance(self.tags.get("tags"), dict):
                container = self.tags.get("tags") or {}
            
            if isinstance(container.get("tags"), list):
                tags = [str(t).strip().lower() for t in container.get("tags") if str(t).strip()]
        return tags
    
    def get_paper_title(self) -> str:
        """Get paper title from structured summary if available."""
        if self.structured_summary and self.structured_summary.paper_info:
            return self.structured_summary.paper_info.title_zh or self.structured_summary.paper_info.title_en
        return self.arxiv_id
    
    def get_one_sentence_summary(self) -> str:
        """Get one sentence summary from structured summary if available."""
        if self.structured_summary:
            return self.structured_summary.one_sentence_summary
        return ""
    
    def get_innovations(self) -> List[Dict[str, str]]:
        """Get innovations from structured summary if available."""
        if self.structured_summary:
            return [
                {
                    "title": innovation.title,
                    "description": innovation.description,
                    "improvement": innovation.improvement,
                    "significance": innovation.significance
                }
                for innovation in self.structured_summary.innovations
            ]
        return []
    
    def get_results(self) -> Dict[str, List[str]]:
        """Get results from structured summary if available."""
        if self.structured_summary:
            return {
                "experimental_highlights": self.structured_summary.results.experimental_highlights,
                "practical_value": self.structured_summary.results.practical_value
            }
        return {"experimental_highlights": [], "practical_value": []}
    
    def get_terminology(self) -> List[Dict[str, str]]:
        """Get terminology from structured summary if available."""
        if self.structured_summary:
            return [
                {
                    "term": term.term,
                    "definition": term.definition
                }
                for term in self.structured_summary.terminology
            ]
        return []


class ServiceData:
    """Service data structure for paper metadata."""
    
    def __init__(self, source_type: str = "system", user_id: Optional[str] = None, 
                 original_url: Optional[str] = None):
        self.source_type = source_type
        self.user_id = user_id
        self.original_url = original_url
