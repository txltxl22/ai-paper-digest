"""
Summary detail services for loading and rendering individual papers.
"""
from typing import Optional, Dict, Any
from pathlib import Path
import json
import markdown
from .models import SummaryData, ServiceData
from summary_service.record_manager import get_structured_summary, get_tags
from summary_service.models import SummaryRecord


class SummaryLoader:
    """Service for loading individual summary data."""
    
    def __init__(self, summary_dir):
        # Import here to avoid circular imports
        from summary_service.record_manager import load_summary_with_service_record
        self._load_summary = load_summary_with_service_record
        self.summary_dir = summary_dir
    
    def load_summary(self, arxiv_id: str) -> Optional[SummaryRecord]:
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
    
    def render_summary(self, record: SummaryRecord) -> Dict[str, Any]:
        """Render a complete summary for display using SummaryRecord model."""
        # Extract data from Pydantic models
        structured_summary = record.summary_data.structured_content
        tags_obj = record.summary_data.tags
        content = record.summary_data.markdown_content
        
        # If content is empty, generate from structured content
        if not content:
                        content = structured_summary.to_markdown()
        
        # If content is still empty, show a message
        if not content:
            arxiv_id = record.service_data.arxiv_id
            content = f"## 📄 论文总结\n\n**{arxiv_id}**\n\n⚠️ 内容暂时不可用\n\n该论文的摘要内容当前不可用。请稍后再试或联系管理员。"
        
        # Render HTML content
        html_content = self.render_markdown(content)
        
        # Get abstract from PaperInfo
        abstract = structured_summary.paper_info.abstract
        
        # Extract tags
        top_tags = [str(t).strip().lower() for t in (tags_obj.top or []) if str(t).strip()]
        detail_tags = [str(t).strip().lower() for t in (tags_obj.tags or []) if str(t).strip()]
        
        return {
            "html_content": html_content,
            "top_tags": top_tags,
            "detail_tags": detail_tags,
            "source_type": record.service_data.source_type or "system",
            "user_id": record.service_data.user_id,
            "original_url": record.service_data.original_url,
            "structured_summary": structured_summary,
            "paper_title": structured_summary.paper_info.title_zh,
            "one_sentence_summary": structured_summary.one_sentence_summary,
            "innovations": [{"title": i.title, "description": i.description, "improvement": i.improvement, "significance": i.significance} for i in structured_summary.innovations],
            "results": {"experimental_highlights": structured_summary.results.experimental_highlights, "practical_value": structured_summary.results.practical_value},
            "terminology": [{"term": t.term, "definition": t.definition} for t in structured_summary.terminology],
            "abstract": abstract  # From PaperInfo
        }
