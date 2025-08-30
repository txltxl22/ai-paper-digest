"""
Summary detail services for loading and rendering individual papers.
"""
from typing import Optional, Dict, Any
from pathlib import Path
import markdown
from .models import SummaryData, ServiceData


class SummaryLoader:
    """Service for loading individual summary data."""
    
    def __init__(self, summary_dir):
        # Import here to avoid circular imports
        from summary_service.record_manager import load_summary_with_service_record
        self._load_summary = load_summary_with_service_record
        self.summary_dir = summary_dir
    
    def load_summary(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """Load summary data for a specific paper."""
        return self._load_summary(arxiv_id, self.summary_dir)


class SummaryRenderer:
    """Service for rendering summary content."""
    
    def render_markdown(self, md_text: str) -> str:
        """Convert Markdown → HTML (GitHub-flavoured-ish)."""
        return markdown.markdown(
            md_text,
            extensions=[
                "fenced_code",
                "tables", 
                "codehilite",
                "toc",
                "attr_list",
            ],
        )
    
    def render_summary(self, summary_data: Dict[str, Any], service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Render a complete summary for display."""
        # Extract data
        content = summary_data.get("content", "")
        tags_dict = summary_data.get("tags", {})
        
        # Create model objects
        summary = SummaryData(
            arxiv_id=summary_data.get("arxiv_id", ""),
            content=content,
            tags=tags_dict
        )
        
        service = ServiceData(
            source_type=service_data.get("source_type", "system"),
            user_id=service_data.get("user_id"),
            original_url=service_data.get("original_url")
        )
        
        # Render HTML content
        html_content = self.render_markdown(content)
        
        return {
            "html_content": html_content,
            "tags": summary.get_all_tags(),
            "source_type": service.source_type,
            "user_id": service.user_id,
            "original_url": service.original_url
        }
