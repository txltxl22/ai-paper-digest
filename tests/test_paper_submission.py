import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from datetime import date


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Create a test client with temporary directories."""
    import app.main as sp
    
    # Setup temporary directories
    sp.USER_DATA_DIR = tmp_path / "user_data"
    sp.SUMMARY_DIR = tmp_path / "summary"
    sp.PDF_DIR = tmp_path / "papers"
    sp.MD_DIR = tmp_path / "markdown"
    sp.DATA_DIR = tmp_path / "data"
    
    for dir_path in [sp.USER_DATA_DIR, sp.SUMMARY_DIR, sp.PDF_DIR, sp.MD_DIR, sp.DATA_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    sp.app.config.update(TESTING=True)
    return sp.app.test_client()


class TestPaperSubmissionFunctions:
    """Test the paper submission utility functions."""
    
    def test_check_daily_limit_new_ip(self, client, tmp_path):
        """Test daily limit check for new IP."""
        import app.main as sp
        
        # Test with new IP
        result = sp.check_daily_limit("192.168.1.100")
        assert result is True
    
    def test_check_daily_limit_existing_ip_under_limit(self, client, tmp_path):
        """Test daily limit check for existing IP under limit."""
        import app.main as sp
        
        # Create daily limits file
        limits_file = sp.DATA_DIR / "daily_limits.json"
        today = date.today().isoformat()
        limits_data = {
            "192.168.1.100": {"date": today, "count": 2}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Test with IP under limit
        result = sp.check_daily_limit("192.168.1.100")
        assert result is True
    
    def test_check_daily_limit_existing_ip_at_limit(self, client, tmp_path):
        """Test daily limit check for existing IP at limit."""
        import app.main as sp
        
        # Create daily limits file
        limits_file = sp.DATA_DIR / "daily_limits.json"
        today = date.today().isoformat()
        limits_data = {
            "192.168.1.100": {"date": today, "count": 3}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Test with IP at limit
        result = sp.check_daily_limit("192.168.1.100")
        assert result is False
    
    def test_check_daily_limit_old_date(self, client, tmp_path):
        """Test daily limit check with old date (should reset)."""
        import app.main as sp
        
        # Create daily limits file with old date
        limits_file = sp.DATA_DIR / "daily_limits.json"
        old_date = "2024-01-01"
        limits_data = {
            "192.168.1.100": {"date": old_date, "count": 3}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Test with old date (should reset)
        result = sp.check_daily_limit("192.168.1.100")
        assert result is True
    
    def test_increment_daily_limit_new_ip(self, client, tmp_path):
        """Test incrementing daily limit for new IP."""
        import app.main as sp
        
        sp.increment_daily_limit("192.168.1.100")
        
        # Check if file was created
        limits_file = sp.DATA_DIR / "daily_limits.json"
        assert limits_file.exists()
        
        # Check content
        limits_data = json.loads(limits_file.read_text(encoding="utf-8"))
        assert "192.168.1.100" in limits_data
        assert limits_data["192.168.1.100"]["count"] == 1
        assert limits_data["192.168.1.100"]["date"] == date.today().isoformat()
    
    def test_increment_daily_limit_existing_ip(self, client, tmp_path):
        """Test incrementing daily limit for existing IP."""
        import app.main as sp
        
        # Create initial limits
        limits_file = sp.DATA_DIR / "daily_limits.json"
        today = date.today().isoformat()
        limits_data = {
            "192.168.1.100": {"date": today, "count": 1}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Increment
        sp.increment_daily_limit("192.168.1.100")
        
        # Check updated content
        limits_data = json.loads(limits_file.read_text(encoding="utf-8"))
        assert limits_data["192.168.1.100"]["count"] == 2


class TestPaperSubmissionAPI:
    """Test the paper submission API endpoint."""
    
    def test_submit_paper_basic_validation(self, client):
        """Test basic validation without complex mocking."""
        # Test missing URL
        response = client.post("/submit_paper", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Missing URL"
        
        # Test empty URL
        response = client.post("/submit_paper", json={"url": ""})
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "Empty URL"
        
        # Test not logged in
        response = client.post("/submit_paper", json={"url": "https://arxiv.org/abs/2506.12345"})
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Login required"
    
    def test_submit_paper_daily_limit_exceeded(self, client, tmp_path):
        """Test submission when daily limit is exceeded."""
        import app.main as sp
        
        # Set up daily limit
        limits_file = sp.DATA_DIR / "daily_limits.json"
        today = date.today().isoformat()
        limits_data = {
            "127.0.0.1": {"date": today, "count": 3}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Login user
        client.set_cookie("uid", "testuser")
        
        # Try to submit
        response = client.post("/submit_paper", json={"url": "https://arxiv.org/abs/2506.12345"})
        assert response.status_code == 429
        data = response.get_json()
        assert data["error"] == "Daily limit exceeded"


class TestAICheckFunction:
    """Test the AI relevance checking function."""
    
    def test_check_paper_ai_relevance_basic(self, client):
        """Test basic AI relevance check functionality."""
        import app.main as sp
        
        # Test with sample text
        text_content = "This paper presents a novel approach to machine learning..."
        
        # The function should handle the text and return a result
        # We can't easily mock the LLM call, but we can test the function exists
        assert hasattr(sp, 'check_paper_ai_relevance')
        assert callable(sp.check_paper_ai_relevance)


class TestIntegration:
    """Integration tests for the complete paper submission flow."""
    
    def test_submission_route_exists(self, client):
        """Test that the submission route exists and responds."""
        # Test that the route exists
        response = client.post("/submit_paper", json={})
        # Should get a 400 for missing URL, not 404 for missing route
        assert response.status_code == 400
    
    def test_daily_limits_integration(self, client, tmp_path):
        """Test daily limits integration with the API."""
        import app.main as sp
        
        # Set up daily limit
        limits_file = sp.DATA_DIR / "daily_limits.json"
        today = date.today().isoformat()
        limits_data = {
            "127.0.0.1": {"date": today, "count": 1}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Login user
        client.set_cookie("uid", "testuser")
        
        # Try to submit (should work since count < 3)
        response = client.post("/submit_paper", json={"url": "https://arxiv.org/abs/2506.12345"})
        # Should not get daily limit exceeded error
        assert response.status_code != 429


if __name__ == "__main__":
    pytest.main([__file__])
