"""
Test cases for URL tracking and AI judgment caching functionality.
Tests URL saving, retrieval, and AI judgment caching.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest
from datetime import datetime

from app.paper_submission.user_data import UserDataManager
from app.paper_submission.ai_checker import AIContentChecker
from app.paper_submission.ai_cache import AICacheManager


class TestURLTracking:
    """Test URL tracking functionality."""
    
    def test_save_uploaded_url_new_user(self, tmp_path):
        """Test saving uploaded URL for a new user."""
        # Create UserDataManager with temp directory
        user_data_manager = UserDataManager(tmp_path)
        
        # Test data
        uid = "test_user"
        url = "https://fake-arxiv.org/abs/9999.99999"
        ai_result = (True, 0.95, ["machine learning", "neural networks"])
        process_result = {
            "success": True,
            "summary_path": "/path/to/summary.md",
            "paper_subject": "Machine Learning"
        }
        
        # Save uploaded URL
        user_data_manager.save_uploaded_url(uid, url, ai_result, process_result)
        
        # Get uploaded URLs
        uploaded_urls = user_data_manager.get_uploaded_urls(uid)
        
        # Verify data
        assert len(uploaded_urls) == 1
        
        upload_record = uploaded_urls[0]
        assert upload_record["url"] == url
        assert upload_record["ai_judgment"]["is_ai"] == ai_result[0]
        assert upload_record["ai_judgment"]["confidence"] == ai_result[1]
        assert upload_record["ai_judgment"]["tags"] == ai_result[2]
        assert upload_record["process_result"]["success"] == process_result["success"]
        assert upload_record["process_result"]["summary_path"] == process_result["summary_path"]
        assert upload_record["process_result"]["paper_subject"] == process_result["paper_subject"]
        assert "timestamp" in upload_record
    
    def test_save_uploaded_url_existing_user(self, tmp_path):
        """Test saving uploaded URL for existing user."""
        # Create UserDataManager with temp directory
        user_data_manager = UserDataManager(tmp_path)
        
        # Create existing user data file manually
        user_file = tmp_path / "test_user.json"
        existing_data = {
            "read": {"9999.99999": "2025-08-30T10:00:00+08:00"},
            "events": [],
            "uploaded_urls": [
                {
                    "url": "https://fake-arxiv.org/abs/9999.11111",
                    "timestamp": "2025-08-30T09:00:00+08:00",
                    "ai_judgment": {"is_ai": True, "confidence": 0.9, "tags": []},
                    "process_result": {"success": True, "error": None}
                }
            ]
        }
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f)
        
        # Test data
        uid = "test_user"
        url = "https://fake-arxiv.org/abs/9999.99999"
        ai_result = (False, 0.3, ["statistics"])
        process_result = {
            "success": False,
            "error": "Not AI paper"
        }
        
        # Save uploaded URL
        user_data_manager.save_uploaded_url(uid, url, ai_result, process_result)
        
        # Get uploaded URLs
        uploaded_urls = user_data_manager.get_uploaded_urls(uid)
        
        # Verify data
        assert len(uploaded_urls) == 2
        
        # Check new record
        new_record = uploaded_urls[1]
        assert new_record["url"] == url
        assert new_record["ai_judgment"]["is_ai"] == ai_result[0]
        assert new_record["ai_judgment"]["confidence"] == ai_result[1]
        assert new_record["ai_judgment"]["tags"] == ai_result[2]
        assert new_record["process_result"]["success"] == process_result["success"]
        assert new_record["process_result"]["error"] == process_result["error"]
    
    def test_get_uploaded_urls_existing_user(self, tmp_path):
        """Test getting uploaded URLs for existing user."""
        # Create UserDataManager with temp directory
        user_data_manager = UserDataManager(tmp_path)
        
        # Create user data with uploaded URLs
        user_file = tmp_path / "test_user.json"
        user_data = {
            "read": {"9999.99999": "2025-08-30T10:00:00+08:00"},
            "events": [],
            "uploaded_urls": [
                {
                    "url": "https://fake-arxiv.org/abs/9999.11111",
                    "timestamp": "2025-08-30T09:00:00+08:00",
                    "ai_judgment": {"is_ai": True, "confidence": 0.9, "tags": []},
                    "process_result": {"success": True, "error": None}
                },
                {
                    "url": "https://fake-arxiv.org/abs/9999.22222",
                    "timestamp": "2025-08-30T10:00:00+08:00",
                    "ai_judgment": {"is_ai": False, "confidence": 0.2, "tags": []},
                    "process_result": {"success": False, "error": "Not AI paper"}
                }
            ]
        }
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f)
        
        # Get uploaded URLs
        uploaded_urls = user_data_manager.get_uploaded_urls("test_user")
        
        assert len(uploaded_urls) == 2
        assert uploaded_urls[0]["url"] == "https://fake-arxiv.org/abs/9999.11111"
        assert uploaded_urls[1]["url"] == "https://fake-arxiv.org/abs/9999.22222"
        assert uploaded_urls[0]["ai_judgment"]["is_ai"] is True
        assert uploaded_urls[1]["ai_judgment"]["is_ai"] is False
    
    def test_get_uploaded_urls_new_user(self, tmp_path):
        """Test getting uploaded URLs for new user."""
        # Create UserDataManager with temp directory
        user_data_manager = UserDataManager(tmp_path)
        
        # Get uploaded URLs for new user
        uploaded_urls = user_data_manager.get_uploaded_urls("new_user")
        
        assert uploaded_urls == []
    
    def test_get_uploaded_urls_missing_section(self, tmp_path):
        """Test getting uploaded URLs when section is missing."""
        # Create UserDataManager with temp directory
        user_data_manager = UserDataManager(tmp_path)
        
        # Create user data without uploaded_urls section
        user_file = tmp_path / "test_user.json"
        user_data = {
            "read": {"2506.12345": "2025-08-30T10:00:00+08:00"},
            "events": []
            # Missing uploaded_urls section
        }
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f)
        
        # Get uploaded URLs
        uploaded_urls = user_data_manager.get_uploaded_urls("test_user")
        
        assert uploaded_urls == []


class TestAICaching:
    """Test AI judgment caching functionality."""
    
    def test_ai_cache_manager_structure(self, tmp_path):
        """Test that AI cache manager has the correct structure."""
        cache_file = tmp_path / "ai_cache.json"
        ai_cache_manager = AICacheManager(cache_file)
        
        # Test that cache manager is initialized
        assert ai_cache_manager.cache_file == cache_file
        
        # Test that cache is empty initially
        stats = ai_cache_manager.get_cache_stats()
        assert stats["cache_size"] == 0
    
    def test_ai_cache_manager_caching(self, tmp_path):
        """Test that AI cache manager can cache and retrieve results."""
        cache_file = tmp_path / "ai_cache.json"
        ai_cache_manager = AICacheManager(cache_file)
        
        # Test caching a result
        ai_cache_manager.cache_result("test_url", True, 0.9, ["machine learning"])
        
        # Test retrieving the result
        result = ai_cache_manager.get_cached_result("test_url")
        assert result is not None
        assert result[0] is True  # is_ai
        assert result[1] == 0.9  # confidence
        assert result[2] == ["machine learning"]  # tags
    
    def test_ai_cache_manager_stats(self, tmp_path):
        """Test that AI cache manager provides statistics."""
        cache_file = tmp_path / "ai_cache.json"
        ai_cache_manager = AICacheManager(cache_file)
        
        # Add some test data
        ai_cache_manager.cache_result("test_url1", True, 0.9, ["ml"])
        ai_cache_manager.cache_result("test_url2", False, 0.3, ["stats"])
        
        # Get stats
        stats = ai_cache_manager.get_cache_stats()
        assert stats["cache_size"] == 2
        assert stats["cache_file"] == str(cache_file)
        assert stats["cache_file_exists"] is True


class TestURLErrorHandling:
    """Test error handling in URL tracking."""
    
    def test_save_uploaded_url_file_error(self, tmp_path):
        """Test handling file write errors."""
        # Create UserDataManager with temp directory
        user_data_manager = UserDataManager(tmp_path)
        
        # Create a directory instead of a file to cause write error
        user_file = tmp_path / "test_user"
        user_file.mkdir()
        
        # Should not raise exception
        user_data_manager.save_uploaded_url("test_user", "https://example.com", (True, 0.9, []), {"success": True})
        
        # Verify error was logged (we can't easily test print statements)
        # The function should handle the error gracefully
    
    def test_get_uploaded_urls_file_error(self, tmp_path):
        """Test handling file read errors."""
        # Create UserDataManager with temp directory
        user_data_manager = UserDataManager(tmp_path)
        
        # Create an invalid JSON file
        user_file = tmp_path / "test_user.json"
        with open(user_file, 'w', encoding='utf-8') as f:
            f.write('{"invalid": json}')
        
        # Should return empty list on error
        uploaded_urls = user_data_manager.get_uploaded_urls("test_user")
        assert uploaded_urls == []


class TestIntegration:
    """Test integration of URL tracking with paper submission."""
    
    def test_url_tracking_integration(self, tmp_path):
        """Test that URL tracking integrates with paper submission flow."""
        # Test that the classes exist and can be instantiated
        user_data_manager = UserDataManager(tmp_path)
        ai_cache_manager = AICacheManager(tmp_path / "ai_cache.json")
        
        # Test that they have the expected methods
        assert hasattr(user_data_manager, 'save_uploaded_url')
        assert hasattr(user_data_manager, 'get_uploaded_urls')
        assert hasattr(ai_cache_manager, 'cache_result')
        assert hasattr(ai_cache_manager, 'get_cached_result')
        
        # Test basic functionality
        user_data_manager.save_uploaded_url("test_user", "https://example.com", (True, 0.9, []), {"success": True})
        uploaded_urls = user_data_manager.get_uploaded_urls("test_user")
        assert len(uploaded_urls) == 1
