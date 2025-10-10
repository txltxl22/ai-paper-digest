"""
Summary detail services for loading and rendering individual papers.
"""
from typing import Optional, Dict, Any
from pathlib import Path
import json
import markdown
from .models import SummaryData, ServiceData
from summary_service.record_manager import get_structured_summary, get_tags


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
    
    def load_structured_summary(self, arxiv_id: str):
        """Load structured summary object for a specific paper."""
        return get_structured_summary(arxiv_id, self.summary_dir)
    
    def load_tags(self, arxiv_id: str):
        """Load tags object for a specific paper."""
        return get_tags(arxiv_id, self.summary_dir)


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
        content = summary_data.get("markdown_content", summary_data.get("content", ""))
        
        # If content is empty or None, try to generate from structured content
        if not content and "structured_content" in summary_data:
            from summary_service.models import parse_summary
            try:
                structured_content = summary_data.get("structured_content", {})
                if structured_content and isinstance(structured_content, dict):
                    if "paper_info" in structured_content:
                        # Convert dictionary to StructuredSummary object
                        structured_summary = parse_summary(json.dumps(structured_content))
                        content = structured_summary.to_markdown()
                    elif "content" in structured_content:
                        # This should not happen anymore with the fix above
                        print(f"Warning: Found legacy content in structured_content")
                        content = structured_content.get("content", "")
            except Exception as e:
                print(f"Error converting structured content to markdown: {e}")
        
        # If content is still empty, show a message
        if not content:
            arxiv_id = service_data.get("arxiv_id", "Unknown")
            content = f"## 📄 论文总结\n\n**{arxiv_id}**\n\n⚠️ 内容暂时不可用\n\n该论文的摘要内容当前不可用。请稍后再试或联系管理员。"
        
        tags_dict = summary_data.get("tags", {})
        
        # Try to load structured summary
        arxiv_id = service_data.get("arxiv_id", "")
        structured_summary = None
        if arxiv_id:
            structured_summary = self.loader.load_structured_summary(arxiv_id) if hasattr(self, 'loader') else None
        
        # Create model objects
        summary = SummaryData(
            arxiv_id=arxiv_id,
            content=content,
            tags=tags_dict,
            structured_summary=structured_summary
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
            "top_tags": summary.get_top_tags(),
            "detail_tags": summary.get_detail_tags(),
            "source_type": service.source_type,
            "user_id": service.user_id,
            "original_url": service.original_url,
            "structured_summary": structured_summary,
            "paper_title": summary.get_paper_title(),
            "one_sentence_summary": summary.get_one_sentence_summary(),
            "innovations": summary.get_innovations(),
            "results": summary.get_results(),
            "terminology": summary.get_terminology()
        }
