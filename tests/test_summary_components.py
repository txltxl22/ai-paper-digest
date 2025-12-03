"""
Unit tests for summary components to catch field name and data structure issues early.
"""
import json
import pytest
from pathlib import Path


class TestSummaryDataStructure:
    """Test summary data structure and field name handling."""
    
    def test_structured_summary_save_format(self, tmp_path):
        """Test that structured summaries are saved with correct field names."""
        from summary_service.models import (
            StructuredSummary, PaperInfo, Innovation, Results, TermDefinition, Tags
        )
        from summary_service.record_manager import save_summary_with_service_record
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a test structured summary
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(
                title_zh="测试论文",
                title_en="Test Paper",
                abstract="Test Abstract"
            ),
            one_sentence_summary="Test summary.",
            innovations=[
                Innovation(
                    title="Test Innovation",
                    description="Test description",
                    improvement="Test improvement",
                    significance="Test significance"
                )
            ],
            results=Results(
                experimental_highlights=["Test highlight"],
                practical_value=["Test value"]
            ),
            terminology=[
                TermDefinition(term="Test Term", definition="Test definition")
            ]
        )
        
        tags = Tags(top=["test"], tags=["test", "unit"])
        
        # Save the structured summary
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Verify the saved format
        json_path = summary_dir / "test.12345.json"
        assert json_path.exists()
        
        with open(json_path, 'r', encoding='utf-8') as f:
            record = json.load(f)
        
        # Check that the correct field names are used
        summary_data = record["summary_data"]
        assert "markdown_content" in summary_data, "Should use 'markdown_content' field"
        assert "structured_content" in summary_data, "Should use 'structured_content' field"
        assert "tags" in summary_data, "Should use 'tags' field"
        
        # Check that structured_content has the correct structure
        structured_content = summary_data["structured_content"]
        assert "paper_info" in structured_content
        assert "one_sentence_summary" in structured_content
        assert "innovations" in structured_content
        assert "results" in structured_content
        assert "terminology" in structured_content
        
        # Check that it's NOT using the old 'content' field
        assert "content" not in summary_data, "Should not use old 'content' field"
    
    def test_index_page_field_handling(self, tmp_path):
        """Test that index page correctly handles markdown_content field."""
        from app.index_page.services import EntryRenderer
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create properly formatted summary using the save function
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="新格式", title_en="New Format", abstract="Test Abstract"),
            one_sentence_summary="This is new format content.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["new"], tags=["new", "format"])
        
        save_summary_with_service_record(
            arxiv_id="new.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Test rendering
        renderer = EntryRenderer(summary_dir)
        
        # Test new format
        new_entry = {"id": "new.12345"}
        new_rendered = renderer.render_page_entries([new_entry])
        assert len(new_rendered) == 1
        new_html = new_rendered[0].get("preview_html", "")
        assert "New Format" in new_html, "New format content should be rendered"
    
    def test_detail_page_field_handling(self, tmp_path):
        """Test that detail page correctly handles structured summary loading."""
        from app.summary_detail.services import SummaryLoader, SummaryRenderer
        from summary_service.record_manager import get_structured_summary
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a properly formatted summary
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试论文", title_en="Test Paper", abstract="Test Abstract"),
            one_sentence_summary="Test summary.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["test"], tags=["test", "unit"])
        
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Test that structured summary can be loaded
        structured_summary = get_structured_summary("test.12345", summary_dir)
        assert structured_summary is not None, "Structured summary should be loadable"
        assert structured_summary.paper_info.title_zh == "测试论文"
        assert structured_summary.paper_info.title_en == "Test Paper"
        
        # Test that detail page can render it
        loader = SummaryLoader(summary_dir)
        renderer = SummaryRenderer()
        renderer.loader = loader
        
        record = loader.load_summary("test.12345")
        assert record is not None
        
        rendered = renderer.render_summary(record)
        
        assert "html_content" in rendered
        assert "paper_title" in rendered
        assert "one_sentence_summary" in rendered
        assert "top_tags" in rendered
        assert "detail_tags" in rendered
        
        # Verify the content
        assert rendered["paper_title"] == "测试论文"
        assert rendered["one_sentence_summary"] == "Test summary."
        assert rendered["top_tags"] == ["test"]
        assert "unit" in rendered["detail_tags"]
    
    def test_tags_structure_handling(self, tmp_path):
        """Test that tags are handled correctly."""
        from app.index_page.services import EntryScanner
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Test case 1: New format tags
        new_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test", abstract="Test Abstract"),
            one_sentence_summary="Content.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        new_tags = Tags(top=["llm"], tags=["machine learning", "ai"])
        
        save_summary_with_service_record(
            arxiv_id="new.12345",
            summary_content=new_summary,
            tags=new_tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Test case 2: Another entry with different tags
        cv_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test", abstract="Test Abstract"),
            one_sentence_summary="Content.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        cv_tags = Tags(top=["cv"], tags=["computer vision", "deep learning"])
        
        save_summary_with_service_record(
            arxiv_id="cv.12345",
            summary_content=cv_summary,
            tags=cv_tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Test scanning
        scanner = EntryScanner(summary_dir)
        entries_meta = scanner.scan_entries_meta()
        
        # Find entries
        new_entry = None
        cv_entry = None
        
        for entry in entries_meta:
            if entry["id"] == "new.12345":
                new_entry = entry
            elif entry["id"] == "cv.12345":
                cv_entry = entry
        
        assert new_entry is not None
        assert cv_entry is not None
        
        # Verify tags are parsed correctly
        assert "llm" in new_entry["top_tags"]
        assert "machine learning" in new_entry["detail_tags"]
        assert "ai" in new_entry["detail_tags"]
        
        assert "cv" in cv_entry["top_tags"]
        assert "computer vision" in cv_entry["detail_tags"]
        assert "deep learning" in cv_entry["detail_tags"]


class TestSummaryServiceRecordManager:
    """Test summary service record manager functionality."""
    
    def test_save_summary_with_service_record_structure(self, tmp_path):
        """Test that save_summary_with_service_record creates correct structure."""
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test data
        summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test", abstract="Test Abstract"),
            one_sentence_summary="Test summary.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["test"], tags=["test", "unit"])
        
        # Save
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system",
            original_url="https://example.com/test"
        )
        
        # Verify structure
        json_path = summary_dir / "test.12345.json"
        assert json_path.exists()
        
        with open(json_path, 'r', encoding='utf-8') as f:
            record = json.load(f)
        
        # Check required fields exist
        assert "service_data" in record
        assert "summary_data" in record
        
        service_data = record["service_data"]
        summary_data = record["summary_data"]
        
        # Check service data fields
        assert "arxiv_id" in service_data
        assert "source_type" in service_data
        assert "created_at" in service_data
        assert "original_url" in service_data
        
        # Check summary data fields
        assert "structured_content" in summary_data
        assert "markdown_content" in summary_data
        assert "tags" in summary_data
        assert "updated_at" in summary_data
        
        # Check that legacy files are also created
        md_path = summary_dir / "test.12345.md"
        tags_path = summary_dir / "test.12345.tags.json"
        
        assert md_path.exists(), "Legacy markdown file should be created"
        assert tags_path.exists(), "Legacy tags file should be created"
    
    def test_load_summary_with_service_record(self, tmp_path):
        """Test that load_summary_with_service_record can load saved records."""
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record, load_summary_with_service_record
        
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create and save test data
        summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test", abstract="Test Abstract"),
            one_sentence_summary="Test summary.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["test"], tags=["test", "unit"])
        
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=summary,
            tags=tags,
            summary_dir=summary_dir,
            source_type="system"
        )
        
        # Load and verify
        record = load_summary_with_service_record("test.12345", summary_dir)
        assert record is not None
        
        assert record.service_data.arxiv_id == "test.12345"
        assert record.service_data.source_type == "system"
        assert record.summary_data.markdown_content is not None
        assert record.summary_data.tags is not None
        
        # Verify tags structure
        tags_obj = record.summary_data.tags
        assert tags_obj.top is not None
        assert tags_obj.tags is not None
        assert "test" in tags_obj.top
        assert "unit" in tags_obj.tags
