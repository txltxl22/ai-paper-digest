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
        
        top_tags = summary.get_top_tags()
        detail_tags = summary.get_detail_tags()
        assert "llm" in top_tags
        assert "ai" in top_tags
        assert "machine learning" in detail_tags
        assert "deep learning" in detail_tags
    
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
        from summary_service.models import SummaryRecord, ServiceRecord, SummaryData, StructuredSummary, PaperInfo, Tags, Results
        from datetime import datetime
        
        renderer = SummaryRenderer()
        
        # Create a proper SummaryRecord object
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test Paper", abstract="Test Abstract"),
            one_sentence_summary="This is a test paper.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["llm"], tags=["machine learning"])
        
        service_record = ServiceRecord(
            arxiv_id="test123",
            source_type="system",
            user_id=None,
            original_url=None,
            created_at=datetime.now().isoformat(),
            first_created_at=datetime.now().isoformat()
        )
        
        summary_data_obj = SummaryData(
            structured_content=structured_summary,
            markdown_content="# Test Paper\n\nThis is a test paper.",
            tags=tags,
            updated_at=datetime.now().isoformat()
        )
        
        record = SummaryRecord(
            service_data=service_record,
            summary_data=summary_data_obj
        )
        
        rendered = renderer.render_summary(record)
        
        assert "html_content" in rendered
        assert "top_tags" in rendered
        assert "detail_tags" in rendered
        assert "source_type" in rendered
        assert "user_id" in rendered
        assert "original_url" in rendered
        
        assert rendered["source_type"] == "system"
        assert "llm" in rendered["top_tags"]
        assert "machine learning" in rendered["detail_tags"]
        assert "<h1" in rendered["html_content"]
    
    def test_separate_tag_extraction(self):
        """Test that top tags and detail tags are extracted separately."""
        from summary_service.models import SummaryRecord, ServiceRecord, SummaryData, StructuredSummary, PaperInfo, Tags, Results
        from datetime import datetime
        
        renderer = SummaryRenderer()
        
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test Paper", abstract="Test Abstract"),
            one_sentence_summary="This is a test paper.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["llm", "nlp"], tags=["machine learning", "natural language processing"])
        
        service_record = ServiceRecord(
            arxiv_id="test123",
            source_type="system",
            user_id=None,
            original_url=None,
            created_at=datetime.now().isoformat(),
            first_created_at=datetime.now().isoformat()
        )
        
        summary_data_obj = SummaryData(
            structured_content=structured_summary,
            markdown_content="# Test Paper\n\nThis is a test paper.",
            tags=tags,
            updated_at=datetime.now().isoformat()
        )
        
        record = SummaryRecord(
            service_data=service_record,
            summary_data=summary_data_obj
        )
        
        rendered = renderer.render_summary(record)
        
        # Test separate tag extraction (bug fix)
        assert "top_tags" in rendered
        assert "detail_tags" in rendered
        assert rendered["top_tags"] == ["llm", "nlp"]
        assert rendered["detail_tags"] == ["machine learning", "natural language processing"]
        
        # Test that top_tags and detail_tags are separate
        assert rendered["top_tags"] == ["llm", "nlp"]
        assert rendered["detail_tags"] == ["machine learning", "natural language processing"]
    
    def test_nested_tag_structure_handling(self):
        """Test handling of tag structure."""
        from summary_service.models import SummaryRecord, ServiceRecord, SummaryData, StructuredSummary, PaperInfo, Tags, Results
        from datetime import datetime
        
        renderer = SummaryRenderer()
        
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test Paper", abstract="Test Abstract"),
            one_sentence_summary="This is a test paper.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["llm", "nlp"], tags=["machine learning", "natural language processing"])
        
        service_record = ServiceRecord(
            arxiv_id="test123",
            source_type="system",
            user_id=None,
            original_url=None,
            created_at=datetime.now().isoformat(),
            first_created_at=datetime.now().isoformat()
        )
        
        summary_data_obj = SummaryData(
            structured_content=structured_summary,
            markdown_content="# Test Paper\n\nThis is a test paper.",
            tags=tags,
            updated_at=datetime.now().isoformat()
        )
        
        record = SummaryRecord(
            service_data=service_record,
            summary_data=summary_data_obj
        )
        
        rendered = renderer.render_summary(record)
        
        # Should handle tag structure correctly
        assert rendered["top_tags"] == ["llm", "nlp"]
        assert rendered["detail_tags"] == ["machine learning", "natural language processing"]