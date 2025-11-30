"""
Web integration tests to catch field name and data structure issues early.
"""
import json
import pytest
from pathlib import Path


class TestWebSummaryDisplay:
    """Test web application summary display functionality."""
    
    def test_index_page_markdown_content_field(self, tmp_path):
        """Test that index page correctly handles 'markdown_content' field."""
        from app.index_page.services import EntryScanner, EntryRenderer
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create properly formatted summary
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test Paper", abstract="Test Abstract"),
            one_sentence_summary="This is test content with markdown_content field.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["test"], tags=["test", "web"])
        
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Test scanning
        scanner = EntryScanner(summary_dir)
        entries_meta = scanner.scan_entries_meta()
        
        assert len(entries_meta) == 1
        entry = entries_meta[0]
        assert entry["id"] == "test.12345"
        
        # Test rendering
        renderer = EntryRenderer(summary_dir)
        rendered_entries = renderer.render_page_entries([entry])
        
        assert len(rendered_entries) == 1
        rendered_entry = rendered_entries[0]
        preview_html = rendered_entry.get("preview_html", "")
        
        assert len(preview_html) > 0, "Preview HTML should be generated"
        assert "Test Paper" in preview_html, "Title should be in preview"
        assert "This is test content" in preview_html, "Content should be in preview"
    
    def test_index_page_content_field_fallback(self, tmp_path):
        """Test that index page correctly handles markdown_content field."""
        from app.index_page.services import EntryScanner, EntryRenderer
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create properly formatted summary
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Legacy Paper", abstract="Test Abstract"),
            one_sentence_summary="This is legacy content with content field.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["legacy"], tags=["legacy", "fallback"])
        
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Test scanning
        scanner = EntryScanner(summary_dir)
        entries_meta = scanner.scan_entries_meta()
        
        assert len(entries_meta) == 1
        entry = entries_meta[0]
        assert entry["id"] == "test.12345"
        
        # Test rendering
        renderer = EntryRenderer(summary_dir)
        rendered_entries = renderer.render_page_entries([entry])
        
        assert len(rendered_entries) == 1
        rendered_entry = rendered_entries[0]
        preview_html = rendered_entry.get("preview_html", "")
        
        assert len(preview_html) > 0, "Preview HTML should be generated"
        assert "Legacy Paper" in preview_html, "Title should be in preview"
        assert "This is legacy content" in preview_html, "Content should be in preview"
    
    def test_detail_page_structured_summary_loading(self, tmp_path):
        """Test that detail page can load and display structured summaries."""
        from app.summary_detail.services import SummaryLoader, SummaryRenderer
        from summary_service.record_manager import get_structured_summary, save_summary_with_service_record
        from summary_service.models import StructuredSummary, PaperInfo, Innovation, Results, TermDefinition, Tags
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create properly formatted structured summary
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(
                title_zh="测试论文",
                title_en="Test Paper",
                abstract="Test Abstract"
            ),
            one_sentence_summary="This is a test summary for web integration.",
            innovations=[
                Innovation(
                    title="Test Innovation",
                    description="A test innovation",
                    improvement="Improves testing",
                    significance="Important for testing"
                )
                    ],
            results=Results(
                experimental_highlights=["Test result"],
                practical_value=["Test value"]
            ),
            terminology=[
                TermDefinition(term="Test Term", definition="A test term definition")
            ]
        )
        
        tags = Tags(top=["test"], tags=["test", "web", "integration"])
        
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Test structured summary loading
        structured_summary = get_structured_summary("test.12345", summary_dir)
        assert structured_summary is not None, "Structured summary should be loadable"
        assert structured_summary.paper_info.title_zh == "测试论文"
        assert structured_summary.paper_info.title_en == "Test Paper"
        assert structured_summary.one_sentence_summary == "This is a test summary for web integration."
        assert len(structured_summary.innovations) == 1
        assert len(structured_summary.terminology) == 1
        
        # Test detail page rendering
        loader = SummaryLoader(summary_dir)
        renderer = SummaryRenderer()
        renderer.loader = loader
        
        record = loader.load_summary("test.12345")
        assert record is not None
        
        rendered = renderer.render_summary(record)
        
        # Check required fields
        assert "html_content" in rendered
        assert "paper_title" in rendered
        assert "one_sentence_summary" in rendered
        assert "top_tags" in rendered
        assert "detail_tags" in rendered
        assert "innovations" in rendered
        assert "terminology" in rendered
        
        # Verify content
        assert rendered["paper_title"] == "测试论文"
        assert rendered["one_sentence_summary"] == "This is a test summary for web integration."
        assert rendered["top_tags"] == ["test"]
        assert "web" in rendered["detail_tags"]
        assert "integration" in rendered["detail_tags"]
        assert len(rendered["innovations"]) == 1
        assert len(rendered["terminology"]) == 1
        
        # Check HTML content (currently just renders markdown, not structured content)
        html_content = rendered["html_content"]
        assert "测试论文" in html_content, "Chinese title should be in HTML"
        assert "Test Paper" in html_content, "English title should be in HTML"
        assert "This is a test summary for web integration" in html_content, "Summary should be in HTML"
        
        # Check structured data is accessible
        assert rendered["paper_title"] == "测试论文", "Paper title should be extracted from structured summary"
        assert rendered["one_sentence_summary"] == "This is a test summary for web integration.", "One sentence summary should be extracted"
        assert len(rendered["innovations"]) == 1, "Innovations should be extracted from structured summary"
        assert len(rendered["terminology"]) == 1, "Terminology should be extracted from structured summary"
