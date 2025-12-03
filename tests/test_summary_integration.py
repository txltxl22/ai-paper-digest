"""
Integration tests for summary generation and web display flow.
"""
import json
import pytest
from pathlib import Path


class TestSummaryGenerationAndDisplayIntegration:
    """Integration tests for the complete summary generation and web display flow."""
    
    def test_structured_summary_save_and_load_flow(self, tmp_path):
        """Test the complete flow from structured summary creation to web display."""
        from summary_service.models import (
            StructuredSummary, PaperInfo, Innovation, Results, TermDefinition, Tags
        )
        from summary_service.record_manager import save_summary_with_service_record, load_summary_with_service_record
        from summary_service.record_manager import get_structured_summary
        from app.index_page.services import EntryScanner, EntryRenderer
        from app.summary_detail.services import SummaryLoader, SummaryRenderer
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a test structured summary
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(
                title_zh="测试论文标题",
                title_en="Test Paper Title",
                abstract="Test Abstract"
            ),
            one_sentence_summary="This is a test summary for integration testing.",
            innovations=[
                Innovation(
                    title="Test Innovation",
                    description="A test innovation description",
                    improvement="Improves upon existing methods",
                    significance="Has important implications"
                )
            ],
            results=Results(
                experimental_highlights=["Test experimental result"],
                practical_value=["Test practical value"]
            ),
            terminology=[
                TermDefinition(term="Test Term", definition="A test term definition")
            ]
        )
        
        # Create test tags
        tags = Tags(top=["test"], tags=["test", "integration", "automated"])
        
        # Save the structured summary
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system",
            original_url="https://example.com/test"
        )
        
        # Test 1: Verify the JSON file was created with correct structure
        json_path = summary_dir / "test.12345.json"
        assert json_path.exists(), "JSON file should be created"
        
        with open(json_path, 'r', encoding='utf-8') as f:
            record = json.load(f)
        
        # Check service data
        assert "service_data" in record
        assert record["service_data"]["arxiv_id"] == "test.12345"
        assert record["service_data"]["source_type"] == "system"
        
        # Check summary data structure
        assert "summary_data" in record
        summary_data = record["summary_data"]
        assert "structured_content" in summary_data
        assert "markdown_content" in summary_data
        assert "tags" in summary_data
        
        # Check structured content has correct fields
        structured_content = summary_data["structured_content"]
        assert "paper_info" in structured_content
        assert "one_sentence_summary" in structured_content
        assert "innovations" in structured_content
        assert "results" in structured_content
        assert "terminology" in structured_content
        
        # Test 2: Verify the structured summary can be loaded back
        loaded_record = load_summary_with_service_record("test.12345", summary_dir)
        assert loaded_record is not None
        assert loaded_record.service_data.arxiv_id == "test.12345"
        
        # Test 3: Verify get_structured_summary works
        loaded_structured_summary = get_structured_summary("test.12345", summary_dir)
        assert loaded_structured_summary is not None
        assert loaded_structured_summary.paper_info.title_zh == "测试论文标题"
        assert loaded_structured_summary.paper_info.title_en == "Test Paper Title"
        assert loaded_structured_summary.one_sentence_summary == "This is a test summary for integration testing."
        assert len(loaded_structured_summary.innovations) == 1
        assert len(loaded_structured_summary.terminology) == 1
        
        # Test 4: Verify index page can scan and render the summary
        scanner = EntryScanner(summary_dir)
        entries_meta = scanner.scan_entries_meta()
        
        # Find our test entry
        test_entry = None
        for entry in entries_meta:
            if entry["id"] == "test.12345":
                test_entry = entry
                break
        
        assert test_entry is not None, "Entry should be found in index page scan"
        assert test_entry["source_type"] == "system"
        assert "test" in test_entry["top_tags"]
        assert "integration" in test_entry["detail_tags"]
        
        # Test 5: Verify index page can render the summary content
        renderer = EntryRenderer(summary_dir)
        rendered_entries = renderer.render_page_entries([test_entry])
        
        assert len(rendered_entries) == 1
        rendered_entry = rendered_entries[0]
        preview_html = rendered_entry.get("preview_html", "")
        
        assert len(preview_html) > 0, "Preview HTML should be generated"
        assert "测试论文标题" in preview_html, "Chinese title should be in preview"
        assert "Test Paper Title" in preview_html, "English title should be in preview"
        assert "一句话总结" in preview_html, "Summary section should be in preview"
        
        # Test 6: Verify detail page can load and render the summary
        detail_loader = SummaryLoader(summary_dir)
        detail_renderer = SummaryRenderer()
        detail_renderer.loader = detail_loader
        
        detail_record = detail_loader.load_summary("test.12345")
        assert detail_record is not None
        
        rendered_detail = detail_renderer.render_summary(detail_record)
        
        assert "html_content" in rendered_detail
        assert "top_tags" in rendered_detail
        assert "detail_tags" in rendered_detail
        assert "paper_title" in rendered_detail
        assert "one_sentence_summary" in rendered_detail
        
        html_content = rendered_detail["html_content"]
        assert "测试论文标题" in html_content, "Chinese title should be in detail HTML"
        assert "Test Paper Title" in html_content, "English title should be in detail HTML"
        assert "一句话总结" in html_content, "Summary section should be in detail HTML"
        
        # Test 7: Verify tags are properly loaded
        assert rendered_detail["top_tags"] == ["test"]
        assert "integration" in rendered_detail["detail_tags"]
        assert "automated" in rendered_detail["detail_tags"]
        
        # Test 8: Verify structured summary data is accessible
        assert rendered_detail["paper_title"] == "测试论文标题"
        assert rendered_detail["one_sentence_summary"] == "This is a test summary for integration testing."
        assert len(rendered_detail["innovations"]) == 1
        assert len(rendered_detail["terminology"]) == 1
    
