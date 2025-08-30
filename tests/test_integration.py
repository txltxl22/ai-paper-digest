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
        
        # Create a test summary for detail page
        test_data = {
            "service_data": {
                "source_type": "system",
                "user_id": None,
                "original_url": None
            },
            "summary_data": {
                "arxiv_id": "test.12345",
                "content": "# Test Paper\n\nThis is a test paper.",
                "tags": {
                    "top": ["test"],
                    "tags": ["test", "example"]
                }
            }
        }
        (sp.SUMMARY_DIR / "test.12345.json").write_text(json.dumps(test_data), encoding="utf-8")
        
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
        
        # Create a test summary for detail page
        test_data = {
            "service_data": {
                "source_type": "system",
                "user_id": None,
                "original_url": None
            },
            "summary_data": {
                "arxiv_id": "test.12345",
                "content": "# Test Paper\n\nThis is a test paper.",
                "tags": {
                    "top": ["test"],
                    "tags": ["test", "example"]
                }
            }
        }
        (sp.SUMMARY_DIR / "test.12345.json").write_text(json.dumps(test_data), encoding="utf-8")
        
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
        
        # Create a test summary for detail page
        test_data = {
            "service_data": {
                "source_type": "system",
                "user_id": None,
                "original_url": None
            },
            "summary_data": {
                "arxiv_id": "test.12345",
                "content": "# Test Paper\n\nThis is a test paper.",
                "tags": {
                    "top": ["test"],
                    "tags": ["test", "example"]
                }
            }
        }
        (sp.SUMMARY_DIR / "test.12345.json").write_text(json.dumps(test_data), encoding="utf-8")
        
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
