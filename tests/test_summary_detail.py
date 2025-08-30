"""
Tests for the summary detail subsystem.
"""
import pytest
from pathlib import Path
from app.summary_detail.models import SummaryData, ServiceData
from app.summary_detail.services import SummaryRenderer


class TestSummaryDetailSubsystem:
    """Test the summary detail subsystem."""
    
    def test_summary_data_creation(self):
        """Test SummaryData model creation and tag extraction."""
        tags = {
            "top": ["llm", "ai"],
            "tags": ["machine learning", "deep learning"]
        }
        summary = SummaryData("test123", "Test content", tags)
        
        assert summary.arxiv_id == "test123"
        assert summary.content == "Test content"
        assert summary.tags == tags
        
        all_tags = summary.get_all_tags()
        assert "llm" in all_tags
        assert "ai" in all_tags
        assert "machine learning" in all_tags
        assert "deep learning" in all_tags
    
    def test_service_data_creation(self):
        """Test ServiceData model creation."""
        service = ServiceData("user", "user123", "https://example.com")
        
        assert service.source_type == "user"
        assert service.user_id == "user123"
        assert service.original_url == "https://example.com"
    
    def test_summary_rendering(self):
        """Test summary rendering functionality."""
        renderer = SummaryRenderer()
        
        # Test markdown rendering
        md_content = "# Test Title\n\nThis is **bold** text."
        html_content = renderer.render_markdown(md_content)
        
        assert "<h1" in html_content
        assert "Test Title" in html_content
        assert "<strong>bold</strong>" in html_content or "**bold**" in html_content
    
    def test_summary_renderer_integration(self):
        """Test the complete summary rendering process."""
        renderer = SummaryRenderer()
        
        summary_data = {
            "arxiv_id": "test123",
            "content": "# Test Paper\n\nThis is a test paper.",
            "tags": {
                "top": ["llm"],
                "tags": ["machine learning"]
            }
        }
        
        service_data = {
            "source_type": "system",
            "user_id": None,
            "original_url": None
        }
        
        rendered = renderer.render_summary(summary_data, service_data)
        
        assert "html_content" in rendered
        assert "tags" in rendered
        assert "source_type" in rendered
        assert "user_id" in rendered
        assert "original_url" in rendered
        
        assert rendered["source_type"] == "system"
        assert "llm" in rendered["tags"]
        assert "machine learning" in rendered["tags"]
        assert "<h1" in rendered["html_content"]
