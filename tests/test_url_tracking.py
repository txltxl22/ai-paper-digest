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

from summary_page import (
    save_uploaded_url,
    get_uploaded_urls,
    check_paper_ai_relevance,
    _AI_JUDGMENT_CACHE,
    _user_file
)


class TestURLTracking:
    """Test URL tracking functionality."""
    
    def test_save_uploaded_url_new_user(self, tmp_path):
        """Test saving uploaded URL for a new user."""
        # Mock user data file
        user_file = tmp_path / "test_user.json"
        
        with patch('summary_page._user_file') as mock_get_file:
            mock_get_file.return_value = user_file
            
            # Test data
            uid = "test_user"
            url = "https://arxiv.org/abs/2506.12345"
            ai_result = (True, 0.95)
            process_result = {
                "success": True,
                "summary_path": "/path/to/summary.md",
                "paper_subject": "Machine Learning"
            }
            
            # Save uploaded URL
            save_uploaded_url(uid, url, ai_result, process_result)
            
            # Verify file was created
            assert user_file.exists()
            
            # Load and verify data
            with open(user_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
            
            assert "uploaded_urls" in user_data
            assert len(user_data["uploaded_urls"]) == 1
            
            upload_record = user_data["uploaded_urls"][0]
            assert upload_record["url"] == url
            assert upload_record["ai_judgment"]["is_ai"] == ai_result[0]
            assert upload_record["ai_judgment"]["confidence"] == ai_result[1]
            assert upload_record["process_result"]["success"] == process_result["success"]
            assert upload_record["process_result"]["summary_path"] == process_result["summary_path"]
            assert upload_record["process_result"]["paper_subject"] == process_result["paper_subject"]
            assert "timestamp" in upload_record
    
    def test_save_uploaded_url_existing_user(self, tmp_path):
        """Test saving uploaded URL for existing user."""
        # Create existing user data
        user_file = tmp_path / "test_user.json"
        existing_data = {
            "read": {"2506.12345": "2025-08-30T10:00:00+08:00"},
            "events": [],
            "uploaded_urls": [
                {
                    "url": "https://arxiv.org/abs/2506.11111",
                    "timestamp": "2025-08-30T09:00:00+08:00",
                    "ai_judgment": {"is_ai": True, "confidence": 0.9},
                    "process_result": {"success": True, "error": None}
                }
            ]
        }
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f)
        
        with patch('summary_page._user_file') as mock_get_file:
            mock_get_file.return_value = user_file
            
            # Test data
            uid = "test_user"
            url = "https://arxiv.org/abs/2506.12345"
            ai_result = (False, 0.3)
            process_result = {
                "success": False,
                "error": "Not AI paper"
            }
            
            # Save uploaded URL
            save_uploaded_url(uid, url, ai_result, process_result)
            
            # Load and verify data
            with open(user_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
            
            assert len(user_data["uploaded_urls"]) == 2
            
            # Check that original data is preserved
            assert user_data["read"] == existing_data["read"]
            assert user_data["events"] == existing_data["events"]
            
            # Check new record
            new_record = user_data["uploaded_urls"][1]
            assert new_record["url"] == url
            assert new_record["ai_judgment"]["is_ai"] == ai_result[0]
            assert new_record["ai_judgment"]["confidence"] == ai_result[1]
            assert new_record["process_result"]["success"] == process_result["success"]
            assert new_record["process_result"]["error"] == process_result["error"]
    
    def test_get_uploaded_urls_existing_user(self, tmp_path):
        """Test getting uploaded URLs for existing user."""
        # Create user data with uploaded URLs
        user_file = tmp_path / "test_user.json"
        user_data = {
            "read": {"2506.12345": "2025-08-30T10:00:00+08:00"},
            "events": [],
            "uploaded_urls": [
                {
                    "url": "https://arxiv.org/abs/2506.11111",
                    "timestamp": "2025-08-30T09:00:00+08:00",
                    "ai_judgment": {"is_ai": True, "confidence": 0.9},
                    "process_result": {"success": True, "error": None}
                },
                {
                    "url": "https://arxiv.org/abs/2506.22222",
                    "timestamp": "2025-08-30T10:00:00+08:00",
                    "ai_judgment": {"is_ai": False, "confidence": 0.2},
                    "process_result": {"success": False, "error": "Not AI paper"}
                }
            ]
        }
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f)
        
        with patch('summary_page._user_file') as mock_get_file:
            mock_get_file.return_value = user_file
            
            # Get uploaded URLs
            uploaded_urls = get_uploaded_urls("test_user")
            
            assert len(uploaded_urls) == 2
            assert uploaded_urls[0]["url"] == "https://arxiv.org/abs/2506.11111"
            assert uploaded_urls[1]["url"] == "https://arxiv.org/abs/2506.22222"
            assert uploaded_urls[0]["ai_judgment"]["is_ai"] is True
            assert uploaded_urls[1]["ai_judgment"]["is_ai"] is False
    
    def test_get_uploaded_urls_new_user(self, tmp_path):
        """Test getting uploaded URLs for new user."""
        user_file = tmp_path / "new_user.json"
        
        with patch('summary_page._user_file') as mock_get_file:
            mock_get_file.return_value = user_file
            
            # Get uploaded URLs for new user
            uploaded_urls = get_uploaded_urls("new_user")
            
            assert uploaded_urls == []
    
    def test_get_uploaded_urls_missing_section(self, tmp_path):
        """Test getting uploaded URLs when section is missing."""
        # Create user data without uploaded_urls section
        user_file = tmp_path / "test_user.json"
        user_data = {
            "read": {"2506.12345": "2025-08-30T10:00:00+08:00"},
            "events": []
            # Missing uploaded_urls section
        }
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f)
        
        with patch('summary_page._user_file') as mock_get_file:
            mock_get_file.return_value = user_file
            
            # Get uploaded URLs
            uploaded_urls = get_uploaded_urls("test_user")
            
            assert uploaded_urls == []


class TestAICaching:
    """Test AI judgment caching functionality."""
    
    def test_ai_judgment_cache_structure(self):
        """Test that AI judgment cache has the correct structure."""
        global _AI_JUDGMENT_CACHE
        
        # Clear cache
        _AI_JUDGMENT_CACHE.clear()
        
        # Test that cache is a dictionary
        assert isinstance(_AI_JUDGMENT_CACHE, dict)
        
        # Test that cache is empty initially
        assert len(_AI_JUDGMENT_CACHE) == 0
    
    def test_ai_judgment_function_signature(self):
        """Test that check_paper_ai_relevance function has correct signature."""
        # Test that function accepts optional url parameter
        import inspect
        sig = inspect.signature(check_paper_ai_relevance)
        
        # Should have text_content as first parameter
        assert 'text_content' in sig.parameters
        
        # Should have url as optional parameter
        assert 'url' in sig.parameters
        assert sig.parameters['url'].default is None
    
    def test_ai_judgment_cache_global_access(self):
        """Test that AI judgment cache is accessible globally."""
        global _AI_JUDGMENT_CACHE
        
        # Test that we can access the cache
        assert isinstance(_AI_JUDGMENT_CACHE, dict)
        
        # Test that we can modify the cache
        _AI_JUDGMENT_CACHE['test_key'] = {'is_ai': True, 'confidence': 0.9, 'timestamp': '2025-08-30T10:00:00+08:00'}
        assert 'test_key' in _AI_JUDGMENT_CACHE
        
        # Clean up
        _AI_JUDGMENT_CACHE.pop('test_key', None)


class TestURLErrorHandling:
    """Test error handling in URL tracking."""
    
    def test_save_uploaded_url_file_error(self, tmp_path):
        """Test handling file write errors."""
        # Create a directory instead of a file to cause write error
        user_file = tmp_path / "test_user"
        user_file.mkdir()
        
        with patch('summary_page._user_file') as mock_get_file:
            mock_get_file.return_value = user_file
            
            # Should not raise exception
            save_uploaded_url("test_user", "https://example.com", (True, 0.9), {"success": True})
            
            # Verify error was logged (we can't easily test print statements)
            # The function should handle the error gracefully
    
    def test_get_uploaded_urls_file_error(self, tmp_path):
        """Test handling file read errors."""
        # Create an invalid JSON file
        user_file = tmp_path / "test_user.json"
        with open(user_file, 'w', encoding='utf-8') as f:
            f.write('{"invalid": json}')
        
        with patch('summary_page._user_file') as mock_get_file:
            mock_get_file.return_value = user_file
            
            # Should return empty list on error
            uploaded_urls = get_uploaded_urls("test_user")
            assert uploaded_urls == []


class TestIntegration:
    """Test integration of URL tracking with paper submission."""
    
    def test_url_tracking_integration(self, tmp_path):
        """Test that URL tracking integrates with paper submission flow."""
        # This test would require more complex mocking of the paper submission flow
        # For now, we'll test the basic integration points
        
        # Test that the functions exist and are callable
        assert callable(save_uploaded_url)
        assert callable(get_uploaded_urls)
        assert callable(check_paper_ai_relevance)
        
        # Test that global cache exists
        assert isinstance(_AI_JUDGMENT_CACHE, dict)
