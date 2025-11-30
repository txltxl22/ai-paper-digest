"""
Feed service integration tests to catch specific bugs we encountered.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch


class TestFeedServiceIntegration:
    """Test feed service integration with structured summaries."""
    
    def test_feed_service_tags_object_handling(self, tmp_path):
        """Test that feed service correctly handles Tags objects."""
        from summary_service.models import Tags
        from summary_service.record_manager import save_summary_with_service_record
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a Tags object
        tags = Tags(top=["test"], tags=["test", "integration"])
        
        # Test that Tags object can be converted to dict correctly
        tags_dict = {"tags": tags.tags, "top": tags.top}
        assert tags_dict["top"] == ["test"]
        assert "integration" in tags_dict["tags"]
        
        # Test that save_summary_with_service_record handles Tags objects
        # This simulates what feed_paper_summarizer_service.py does
        from summary_service.models import StructuredSummary, PaperInfo, Results

        summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test", abstract="Test Abstract"),
            one_sentence_summary="Test summary.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Verify the saved structure
        json_path = summary_dir / "test.12345.json"
        assert json_path.exists()
        
        with open(json_path, 'r', encoding='utf-8') as f:
            record = json.load(f)
        
        summary_data = record["summary_data"]
        saved_tags = summary_data["tags"]
        
        # Check that tags were saved as dict, not Tags object
        assert isinstance(saved_tags, dict), "Tags should be saved as dict"
        assert "top" in saved_tags
        assert "tags" in saved_tags
        assert saved_tags["top"] == ["test"]
        assert "integration" in saved_tags["tags"]
    
    def test_feed_service_structured_summary_to_markdown(self, tmp_path):
        """Test that feed service correctly converts StructuredSummary to markdown."""
        from summary_service.models import StructuredSummary, PaperInfo, Results, Tags
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a StructuredSummary object
        summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试论文", title_en="Test Paper", abstract="Test Abstract"),
            one_sentence_summary="This is a test summary for feed service.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        # Test that to_markdown method works correctly
        markdown_content = summary.to_markdown()
        assert isinstance(markdown_content, str), "Should return string"
        assert len(markdown_content) > 0, "Should not be empty"
        assert "测试论文" in markdown_content, "Should contain Chinese title"
        assert "Test Paper" in markdown_content, "Should contain English title"
        assert "一句话总结" in markdown_content, "Should contain summary section"
        
        # Test that this can be saved to a file (simulating feed service behavior)
        md_path = summary_dir / "test.12345.md"
        md_path.write_text(markdown_content, encoding="utf-8")
        
        # Verify the file was created and contains expected content
        assert md_path.exists()
        saved_content = md_path.read_text(encoding="utf-8")
        assert "测试论文" in saved_content
        assert "Test Paper" in saved_content
