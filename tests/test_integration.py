"""
Integration tests for static file accessibility and template consistency.
"""
import json
import pytest
from pathlib import Path


def setup_app_dirs(sp, tmp_path):
    sp.USER_DATA_DIR = tmp_path / "user_data"
    sp.SUMMARY_DIR = tmp_path / "summary"
    sp.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    sp.SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Update the existing modules with test paths
    sp.user_management_module["service"].user_data_dir = sp.USER_DATA_DIR
    sp.user_management_module["service"].admin_user_ids = ["admin1", "admin2"]
    
    sp.index_page_module["scanner"].summary_dir = sp.SUMMARY_DIR
    sp.index_page_module["renderer"].summary_dir = sp.SUMMARY_DIR
    
    sp.summary_detail_module["loader"].summary_dir = sp.SUMMARY_DIR


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
    


class TestStaticFileAccessibility:
    """Test that all necessary static files exist and are accessible."""
    
    def test_static_files_exist_and_accessible(self, tmp_path, monkeypatch):
        """Test that all CSS and JS files referenced in templates exist and are accessible."""
        import app.main as sp
        
        setup_app_dirs(sp, tmp_path)
        sp.app.config.update(TESTING=True)
        client = sp.app.test_client()
        
        # List of static files that should be accessible
        static_files = [
            # CSS files
            ("/assets/base.css", "text/css"),
            ("/static/css/badges.css", "text/css"),
            ("/static/css/components.css", "text/css"),
            ("/static/css/modal.css", "text/css"),
            
            # JS files
            ("/static/js/event-tracker.js", "application/javascript"),
            ("/static/js/theme.js", "application/javascript"),
            ("/static/js/toast.js", "application/javascript"),
            ("/static/js/user-actions.js", "application/javascript"),
            ("/static/js/article-actions.js", "application/javascript"),
            ("/static/js/admin-modal.js", "application/javascript"),
            ("/static/js/paper-submission.js", "application/javascript"),
            
            # Favicon files
            ("/static/favicon.svg", "image/svg+xml"),
        ]
        
        for file_path, expected_mime in static_files:
            response = client.get(file_path)
            assert response.status_code == 200, f"File {file_path} should be accessible"
            assert expected_mime in response.content_type, f"File {file_path} should have correct MIME type"
            assert len(response.data) > 0, f"File {file_path} should not be empty"
    
    def test_template_consistency_between_pages(self, tmp_path, monkeypatch):
        """Test that index and detail pages have consistent template structure."""
        import app.main as sp
        
        setup_app_dirs(sp, tmp_path)
        sp.app.config.update(TESTING=True)
        client = sp.app.test_client()
        
        # Create a test summary for detail page using proper save function
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test Paper", abstract="Test Abstract"),
            one_sentence_summary="This is a test paper.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["test"], tags=["test", "example"])
        
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=sp.SUMMARY_DIR,
            source_type="system"
        )
        
        # Get index page
        index_response = client.get("/")
        assert index_response.status_code == 200
        index_html = index_response.data.decode("utf-8")
        
        # Get detail page
        detail_response = client.get("/summary/test.12345")
        assert detail_response.status_code == 200
        detail_html = detail_response.data.decode("utf-8")
        
        # Check that both pages include the same critical CSS files
        critical_css_files = [
            "base.css",
            "badges.css", 
            "components.css",
            "modal.css"
        ]
        
        for css_file in critical_css_files:
            assert css_file in index_html, f"Index page should include {css_file}"
            assert css_file in detail_html, f"Detail page should include {css_file}"
        
        # Check that both pages include the same critical JS files
        critical_js_files = [
            "event-tracker.js",
            "theme.js",
            "toast.js",
            "user-actions.js",
            "article-actions.js",
            "admin-modal.js",
            "paper-submission.js"
        ]
        
        for js_file in critical_js_files:
            assert js_file in index_html, f"Index page should include {js_file}"
            assert js_file in detail_html, f"Detail page should include {js_file}"
        
        # Check that both pages include admin modal
        assert "admin-progress-modal" in index_html, "Index page should include admin modal"
        assert "admin-progress-modal" in detail_html, "Detail page should include admin modal"
        
        # Check that both pages have proper URL configuration
        assert "window.appUrls" in index_html, "Index page should have appUrls configuration"
        assert "window.appUrls" in detail_html, "Detail page should have appUrls configuration"
    
    def test_night_mode_functionality_included(self, tmp_path, monkeypatch):
        """Test that night mode functionality is properly included in both pages."""
        import app.main as sp
        
        setup_app_dirs(sp, tmp_path)
        sp.app.config.update(TESTING=True)
        client = sp.app.test_client()
        
        # Create a test summary for detail page using proper save function
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test Paper", abstract="Test Abstract"),
            one_sentence_summary="This is a test paper.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["test"], tags=["test", "example"])
        
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=sp.SUMMARY_DIR,
            source_type="system"
        )
        
        # Get index page
        index_response = client.get("/")
        assert index_response.status_code == 200
        index_html = index_response.data.decode("utf-8")
        
        # Get detail page
        detail_response = client.get("/summary/test.12345")
        assert detail_response.status_code == 200
        detail_html = detail_response.data.decode("utf-8")
        
        # Check that both pages include theme.js (night mode functionality)
        assert "theme.js" in index_html, "Index page should include theme.js for night mode"
        assert "theme.js" in detail_html, "Detail page should include theme.js for night mode"
        
        # Check that both pages have the theme toggle button in header
        assert "🌙" in index_html or "☀️" in index_html, "Index page should have theme toggle button"
        assert "🌙" in detail_html or "☀️" in detail_html, "Detail page should have theme toggle button"
        
        # Check that both pages include base.css which contains CSS variables for theming
        assert "base.css" in index_html, "Index page should include base.css for theming"
        assert "base.css" in detail_html, "Detail page should include base.css for theming"
        
        # Check that both pages have proper script loading order (theme.js should be loaded)
        index_scripts = index_html.split('<script src="')
        detail_scripts = detail_html.split('<script src="')
        
        theme_js_found_index = any('theme.js' in script for script in index_scripts)
        theme_js_found_detail = any('theme.js' in script for script in detail_scripts)
        
        assert theme_js_found_index, "Index page should load theme.js script"
        assert theme_js_found_detail, "Detail page should load theme.js script"
    
    def test_essential_components_included(self, tmp_path, monkeypatch):
        """Test that all essential components are included in both pages."""
        import app.main as sp
        
        setup_app_dirs(sp, tmp_path)
        sp.app.config.update(TESTING=True)
        client = sp.app.test_client()
        
        # Create a test summary for detail page using proper save function
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        structured_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="测试", title_en="Test Paper", abstract="Test Abstract"),
            one_sentence_summary="This is a test paper.",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        
        tags = Tags(top=["test"], tags=["test", "example"])
        
        save_summary_with_service_record(
            arxiv_id="test.12345",
            summary_content=structured_summary,
            tags=tags,
            summary_dir=sp.SUMMARY_DIR,
            source_type="system"
        )
        
        # Get index page
        index_response = client.get("/")
        assert index_response.status_code == 200
        index_html = index_response.data.decode("utf-8")
        
        # Get detail page
        detail_response = client.get("/summary/test.12345")
        assert detail_response.status_code == 200
        detail_html = detail_response.data.decode("utf-8")
        
        # Check that both pages include header component
        assert "header" in index_html, "Index page should include header component"
        assert "header" in detail_html, "Detail page should include header component"
        
        # Check that both pages include main content area
        assert "<main>" in index_html, "Index page should have main content area"
        assert "<main>" in detail_html, "Detail page should have main content area"
        
        # Check that both pages have proper HTML structure
        assert "<!doctype html>" in index_html, "Index page should have proper DOCTYPE"
        assert "<!doctype html>" in detail_html, "Detail page should have proper DOCTYPE"
        assert "<html" in index_html, "Index page should have HTML tag"
        assert "<html" in detail_html, "Detail page should have HTML tag"
        assert "<head>" in index_html, "Index page should have head section"
        assert "<head>" in detail_html, "Detail page should have head section"
        assert "<body>" in index_html, "Index page should have body section"
        assert "<body>" in detail_html, "Detail page should have body section"
        
        # Check that both pages have proper meta tags
        assert "charset='utf-8'" in index_html, "Index page should have UTF-8 charset"
        assert "charset='utf-8'" in detail_html, "Detail page should have UTF-8 charset"
        assert 'viewport' in index_html, "Index page should have viewport meta tag"
        assert 'viewport' in detail_html, "Detail page should have viewport meta tag"
        
        # Check that both pages have favicon links
        assert "favicon.svg" in index_html, "Index page should have favicon"
        assert "favicon.svg" in detail_html, "Detail page should have favicon"

    def test_favicon_routes(self, tmp_path, monkeypatch):
        """Test that favicon routes are accessible."""
        import app.main as sp
        
        setup_app_dirs(sp, tmp_path)
        sp.app.config.update(TESTING=True)
        client = sp.app.test_client()
        
        # Test root favicon.ico
        response = client.get('/favicon.ico')
        assert response.status_code == 200
        assert 'image/x-icon' in response.headers['Content-Type'] or 'image/svg+xml' in response.headers['Content-Type']
        
        # Test static favicon.svg
        response = client.get('/static/favicon.svg')
        assert response.status_code == 200
        assert 'image/svg+xml' in response.headers['Content-Type']
