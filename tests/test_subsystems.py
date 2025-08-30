"""
Tests for the new user management and index page subsystems.
"""
import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, date

from app.user_management.factory import create_user_management_module
from app.index_page.factory import create_index_page_module


class TestUserManagementSubsystem:
    """Test the user management subsystem."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.user_data_dir = self.temp_dir / "user_data"
        self.summary_dir = self.temp_dir / "summary"
        self.user_data_dir.mkdir()
        self.summary_dir.mkdir()
        
        # Create user management module
        self.user_module = create_user_management_module(
            user_data_dir=self.user_data_dir,
            admin_user_ids=["admin1", "admin2"]
        )
        self.user_service = self.user_module["service"]
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_user_data_creation(self):
        """Test user data creation and management."""
        user_data = self.user_service.get_user_data("test_user")
        
        # Test initial state
        data = user_data.load()
        assert data["read"] == {}
        assert data["events"] == []
        
        # Test marking as read
        user_data.mark_as_read("paper1")
        read_map = user_data.load_read_map()
        assert "paper1" in read_map
        assert read_map["paper1"] is not None
        
        # Test marking as unread
        user_data.mark_as_unread("paper1")
        read_map = user_data.load_read_map()
        assert "paper1" not in read_map
    
    def test_read_statistics(self):
        """Test read statistics calculation."""
        user_data = self.user_service.get_user_data("test_user")
        
        # Mark some papers as read
        user_data.mark_as_read("paper1")
        user_data.mark_as_read("paper2")
        
        stats = user_data.get_read_stats()
        assert stats["read_total"] == 2
        assert stats["read_today"] >= 0  # Depends on current date
    
    def test_admin_user_check(self):
        """Test admin user validation."""
        assert self.user_service.is_admin_user("admin1") is True
        assert self.user_service.is_admin_user("admin2") is True
        assert self.user_service.is_admin_user("regular_user") is False


class TestIndexPageSubsystem:
    """Test the index page subsystem."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.user_data_dir = self.temp_dir / "user_data"
        self.summary_dir = self.temp_dir / "summary"
        self.user_data_dir.mkdir()
        self.summary_dir.mkdir()
        
        # Create user management module
        self.user_module = create_user_management_module(
            user_data_dir=self.user_data_dir,
            admin_user_ids=["admin1"]
        )
        
        # Create index page module
        self.index_module = create_index_page_module(
            summary_dir=self.summary_dir,
            user_service=self.user_module["service"],
            index_template="<html><body>{{ entries }}</body></html>"
        )
        
        self.entry_scanner = self.index_module["scanner"]
        self.entry_renderer = self.index_module["renderer"]
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_entry_scanning(self):
        """Test entry scanning functionality."""
        # Create a test summary file
        test_summary = {
            "service_data": {
                "source_type": "system",
                "user_id": None,
                "original_url": None
            },
            "summary_data": {
                "content": "# Test Paper\n\nThis is a test paper.",
                "tags": {
                    "top": ["ai", "ml"],
                    "tags": ["machine-learning", "artificial-intelligence"]
                },
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }
        
        summary_file = self.summary_dir / "test_paper.json"
        with open(summary_file, 'w') as f:
            json.dump(test_summary, f)
        
        # Test scanning
        entries = self.entry_scanner.scan_entries_meta()
        assert len(entries) == 1
        assert entries[0]["id"] == "test_paper"
        assert "ai" in entries[0]["top_tags"]
        assert "machine-learning" in entries[0]["detail_tags"]
    
    def test_entry_rendering(self):
        """Test entry rendering functionality."""
        # Create test entry metadata
        entry_meta = {
            "id": "test_paper",
            "updated": datetime.now(),
            "tags": ["ai", "ml"],
            "top_tags": ["ai"],
            "detail_tags": ["ml"],
            "source_type": "system",
            "user_id": None,
            "original_url": None
        }
        
        # Create corresponding summary file
        test_summary = {
            "service_data": {
                "source_type": "system",
                "user_id": None,
                "original_url": None
            },
            "summary_data": {
                "content": "# Test Paper\n\nThis is a test paper.",
                "tags": {
                    "top": ["ai"],
                    "tags": ["ml"]
                }
            }
        }
        
        summary_file = self.summary_dir / "test_paper.json"
        with open(summary_file, 'w') as f:
            json.dump(test_summary, f)
        
        # Test rendering
        rendered = self.entry_renderer.render_page_entries([entry_meta])
        assert len(rendered) == 1
        assert "preview_html" in rendered[0]
        assert "Test Paper" in rendered[0]["preview_html"]
        assert "<h1" in rendered[0]["preview_html"]
    
    def test_tag_cloud(self):
        """Test tag cloud functionality."""
        from app.index_page.models import TagCloud
        
        tag_cloud = TagCloud()
        
        # Create test entries
        entry1 = type('Entry', (), {
            'detail_tags': ['machine-learning', 'ai'],
            'top_tags': ['ai']
        })()
        
        entry2 = type('Entry', (), {
            'detail_tags': ['machine-learning', 'nlp'],
            'top_tags': ['ai']
        })()
        
        # Add entries to tag cloud
        tag_cloud.add_entry(entry1)
        tag_cloud.add_entry(entry2)
        
        # Test tag cloud generation
        tag_cloud_data = tag_cloud.get_tag_cloud()
        assert len(tag_cloud_data) > 0
        
        # Find machine-learning tag
        ml_tag = next((tag for tag in tag_cloud_data if tag["name"] == "machine-learning"), None)
        assert ml_tag is not None
        assert ml_tag["count"] == 2  # Appears in both entries
    
    def test_pagination(self):
        """Test pagination functionality."""
        from app.index_page.models import Pagination
        
        # Test pagination with 25 items, 10 per page
        pagination = Pagination(total_items=25, page=2, per_page=10)
        
        assert pagination.total_pages == 3
        assert pagination.start == 10
        assert pagination.end == 20
        
        # Test page items
        items = list(range(25))
        page_items = pagination.get_page_items(items)
        assert page_items == list(range(10, 20))
