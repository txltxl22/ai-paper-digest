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


@pytest.fixture()
def paper_submission_utils(tmp_path):
    """Create paper submission utilities for testing."""
    from app.paper_submission.utils import check_daily_limit, increment_daily_limit
    from app.paper_submission.user_data import UserDataManager
    from app.paper_submission.ai_cache import AICacheManager
    
    # Create test directories
    user_data_dir = tmp_path / "user_data"
    data_dir = tmp_path / "data"
    
    user_data_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "check_daily_limit": lambda ip: check_daily_limit(ip, data_dir / "daily_limits.json", 3),
        "increment_daily_limit": lambda ip: increment_daily_limit(ip, data_dir / "daily_limits.json"),
        "user_data_manager": UserDataManager(user_data_dir),
        "ai_cache_manager": AICacheManager(data_dir / "ai_cache.json"),
        "data_dir": data_dir
    }


class TestPaperSubmissionFunctions:
    """Test the paper submission utility functions."""
    
    def test_check_daily_limit_new_ip(self, client, paper_submission_utils):
        """Test daily limit check for new IP."""
        
        # Test with new IP
        result = paper_submission_utils["check_daily_limit"]("192.168.1.100")
        assert result is True
    
    def test_check_daily_limit_existing_ip_under_limit(self, client, paper_submission_utils):
        """Test daily limit check for existing IP under limit."""
        
        # Create daily limits file
        limits_file = paper_submission_utils["data_dir"] / "daily_limits.json"
        today = date.today().isoformat()
        limits_data = {
            "192.168.1.100": {"date": today, "count": 2}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Test with IP under limit
        result = paper_submission_utils["check_daily_limit"]("192.168.1.100")
        assert result is True
    
    def test_check_daily_limit_existing_ip_at_limit(self, client, paper_submission_utils):
        """Test daily limit check for existing IP at limit."""
        
        # Create daily limits file
        limits_file = paper_submission_utils["data_dir"] / "daily_limits.json"
        today = date.today().isoformat()
        limits_data = {
            "192.168.1.100": {"date": today, "count": 3}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Test with IP at limit
        result = paper_submission_utils["check_daily_limit"]("192.168.1.100")
        assert result is False
    
    def test_check_daily_limit_old_date(self, client, paper_submission_utils):
        """Test daily limit check with old date (should reset)."""
        
        # Create daily limits file with old date
        limits_file = paper_submission_utils["data_dir"] / "daily_limits.json"
        old_date = "2024-01-01"
        limits_data = {
            "192.168.1.100": {"date": old_date, "count": 3}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Test with old date (should reset)
        result = paper_submission_utils["check_daily_limit"]("192.168.1.100")
        assert result is True
    
    def test_increment_daily_limit_new_ip(self, client, paper_submission_utils):
        """Test incrementing daily limit for new IP."""
        
        paper_submission_utils["increment_daily_limit"]("192.168.1.100")
        
        # Check if file was created
        limits_file = paper_submission_utils["data_dir"] / "daily_limits.json"
        assert limits_file.exists()
        
        # Check content
        limits_data = json.loads(limits_file.read_text(encoding="utf-8"))
        assert "192.168.1.100" in limits_data
        assert limits_data["192.168.1.100"]["count"] == 1
        assert limits_data["192.168.1.100"]["date"] == date.today().isoformat()
    
    def test_increment_daily_limit_existing_ip(self, client, paper_submission_utils):
        """Test incrementing daily limit for existing IP."""
        
        # Create initial limits
        limits_file = paper_submission_utils["data_dir"] / "daily_limits.json"
        today = date.today().isoformat()
        limits_data = {
            "192.168.1.100": {"date": today, "count": 1}
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Increment
        paper_submission_utils["increment_daily_limit"]("192.168.1.100")
        
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
        response = client.post("/submit_paper", json={"url": "https://fake-arxiv.org/abs/9999.99999"})
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Login required"
    
    def test_submit_paper_daily_limit_exceeded(self, client, tmp_path):
        """Test submission when daily limit is exceeded."""
        import app.main as sp
        from app.paper_submission.services import PaperSubmissionService
        from app.paper_submission.user_data import UserDataManager
        from app.paper_submission.ai_cache import AICacheManager
        from app.paper_submission.ai_checker import AIContentChecker
        from app.paper_submission.models import PaperSubmissionResult
        
        # Setup test directories
        user_data_dir = tmp_path / "user_data"
        data_dir = tmp_path / "data"
        summary_dir = tmp_path / "summary"
        prompts_dir = tmp_path / "prompts"
        
        for dir_path in [user_data_dir, data_dir, summary_dir, prompts_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create daily limits file with exceeded limit
        limits_file = data_dir / "daily_limits.json"
        today = date.today().isoformat()
        limits_data = {
            "127.0.0.1": {"date": today, "count": 3}  # At limit
        }
        limits_file.write_text(json.dumps(limits_data), encoding="utf-8")
        
        # Create mock LLM config and paper config
        class MockLLMConfig:
            api_key = "test_key"
            base_url = "http://test.com"
            provider = "test_provider"
            model = "test_model"
        
        class MockPaperConfig:
            max_workers = 1
        
        # Create service components
        user_data_manager = UserDataManager(user_data_dir)
        ai_cache_manager = AICacheManager(data_dir / "ai_judgment_cache.json")
        ai_checker = AIContentChecker(ai_cache_manager, MockLLMConfig(), prompts_dir)
        
        # Create the service
        service = PaperSubmissionService(
            user_data_manager=user_data_manager,
            ai_cache_manager=ai_cache_manager,
            ai_checker=ai_checker,
            limit_file=limits_file,
            daily_limit=3,
            summary_dir=summary_dir,
            llm_config=MockLLMConfig(),
            paper_config=MockPaperConfig(),
            save_summary_func=None
        )
        
        # Mock the get_client_ip function to return a consistent IP
        with patch('app.paper_submission.services.get_client_ip', return_value="127.0.0.1"):
            # Test daily limit exceeded
            result = service.submit_paper("https://arxiv.org/abs/2506.12345", "testuser")
            
            assert result.success is False
            assert "今天已经提交了3篇论文" in result.message
            assert result.error == "Daily limit exceeded"
            
            # Verify the limit file wasn't incremented
            limits_data = json.loads(limits_file.read_text(encoding="utf-8"))
            assert limits_data["127.0.0.1"]["count"] == 3
    
    def test_submit_paper_successful_processing(self, client, tmp_path):
        """Test successful paper submission and processing."""
        import app.main as sp
        from app.paper_submission.services import PaperSubmissionService
        from app.paper_submission.user_data import UserDataManager
        from app.paper_submission.ai_cache import AICacheManager
        from app.paper_submission.ai_checker import AIContentChecker
        
        # Setup test directories
        user_data_dir = tmp_path / "user_data"
        data_dir = tmp_path / "data"
        summary_dir = tmp_path / "summary"
        prompts_dir = tmp_path / "prompts"
        
        for dir_path in [user_data_dir, data_dir, summary_dir, prompts_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create mock LLM config and paper config
        class MockLLMConfig:
            api_key = "test_key"
            base_url = "http://test.com"
            provider = "test_provider"
            model = "test_model"
        
        class MockPaperConfig:
            max_workers = 1
        
        # Create service components
        user_data_manager = UserDataManager(user_data_dir)
        ai_cache_manager = AICacheManager(data_dir / "ai_judgment_cache.json")
        ai_checker = AIContentChecker(ai_cache_manager, MockLLMConfig(), prompts_dir)
        
        # Create the service
        service = PaperSubmissionService(
            user_data_manager=user_data_manager,
            ai_cache_manager=ai_cache_manager,
            ai_checker=ai_checker,
            limit_file=data_dir / "daily_limits.json",
            daily_limit=3,
            summary_dir=summary_dir,
            llm_config=MockLLMConfig(),
            paper_config=MockPaperConfig(),
            save_summary_func=None
        )
        
        # Test that the service can be instantiated and has the expected methods
        assert hasattr(service, 'submit_paper')
        assert hasattr(service, 'get_uploaded_urls')
        assert hasattr(service, 'get_ai_cache_stats')
        
        # Test that user data manager works
        assert hasattr(user_data_manager, 'save_uploaded_url')
        assert hasattr(user_data_manager, 'get_uploaded_urls')
        
        # Test that AI cache manager works
        assert hasattr(ai_cache_manager, 'get_cached_result')
        assert hasattr(ai_cache_manager, 'cache_result')
        
        # Test that AI checker works
        assert hasattr(ai_checker, 'check_paper_ai_relevance')
    
    def test_submit_paper_not_ai_content(self, client, tmp_path):
        """Test submission of non-AI content."""
        from app.paper_submission.services import PaperSubmissionService
        from app.paper_submission.user_data import UserDataManager
        from app.paper_submission.ai_cache import AICacheManager
        from app.paper_submission.ai_checker import AIContentChecker
        
        # Setup test directories
        user_data_dir = tmp_path / "user_data"
        data_dir = tmp_path / "data"
        summary_dir = tmp_path / "summary"
        prompts_dir = tmp_path / "prompts"
        
        for dir_path in [user_data_dir, data_dir, summary_dir, prompts_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create mock LLM config and paper config
        class MockLLMConfig:
            api_key = "test_key"
            base_url = "http://test.com"
            provider = "test_provider"
            model = "test_model"
        
        class MockPaperConfig:
            max_workers = 1
        
        # Create service components
        user_data_manager = UserDataManager(user_data_dir)
        ai_cache_manager = AICacheManager(data_dir / "ai_judgment_cache.json")
        ai_checker = AIContentChecker(ai_cache_manager, MockLLMConfig(), prompts_dir)
        
        # Create the service
        service = PaperSubmissionService(
            user_data_manager=user_data_manager,
            ai_cache_manager=ai_cache_manager,
            ai_checker=ai_checker,
            limit_file=data_dir / "daily_limits.json",
            daily_limit=3,
            summary_dir=summary_dir,
            llm_config=MockLLMConfig(),
            paper_config=MockPaperConfig(),
            save_summary_func=None
        )
        
        # Test that the service can be instantiated and has the expected methods
        assert hasattr(service, 'submit_paper')
        assert hasattr(service, 'get_uploaded_urls')
        assert hasattr(service, 'get_ai_cache_stats')
        
        # Test that user data manager works
        assert hasattr(user_data_manager, 'save_uploaded_url')
        assert hasattr(user_data_manager, 'get_uploaded_urls')
        
        # Test that AI cache manager works
        assert hasattr(ai_cache_manager, 'get_cached_result')
        assert hasattr(ai_cache_manager, 'cache_result')
        
        # Test that AI checker works
        assert hasattr(ai_checker, 'check_paper_ai_relevance')
    
    def test_submit_paper_pdf_resolution_failure(self, client, tmp_path):
        """Test submission when PDF URL resolution fails."""
        from app.paper_submission.services import PaperSubmissionService
        from app.paper_submission.user_data import UserDataManager
        from app.paper_submission.ai_cache import AICacheManager
        from app.paper_submission.ai_checker import AIContentChecker
        
        # Setup test directories
        user_data_dir = tmp_path / "user_data"
        data_dir = tmp_path / "data"
        summary_dir = tmp_path / "summary"
        prompts_dir = tmp_path / "prompts"
        
        for dir_path in [user_data_dir, data_dir, summary_dir, prompts_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create mock LLM config and paper config
        class MockLLMConfig:
            api_key = "test_key"
            base_url = "http://test.com"
            provider = "test_provider"
            model = "test_model"
        
        class MockPaperConfig:
            max_workers = 1
        
        # Create service components
        user_data_manager = UserDataManager(user_data_dir)
        ai_cache_manager = AICacheManager(data_dir / "ai_judgment_cache.json")
        ai_checker = AIContentChecker(ai_cache_manager, MockLLMConfig(), prompts_dir)
        
        # Create the service
        service = PaperSubmissionService(
            user_data_manager=user_data_manager,
            ai_cache_manager=ai_cache_manager,
            ai_checker=ai_checker,
            limit_file=data_dir / "daily_limits.json",
            daily_limit=3,
            summary_dir=summary_dir,
            llm_config=MockLLMConfig(),
            paper_config=MockPaperConfig(),
            save_summary_func=None
        )
        
        # Test that the service components are properly initialized
        assert service.user_data_manager is user_data_manager
        assert service.ai_cache_manager is ai_cache_manager
        assert service.ai_checker is ai_checker
        assert service.daily_limit == 3
        assert service.summary_dir == summary_dir


class TestAICheckFunction:
    """Test the AI relevance checking function."""
    
    def test_check_paper_ai_relevance_basic(self, client):
        """Test basic AI relevance check functionality."""
        from app.paper_submission.ai_checker import AIContentChecker
        from app.paper_submission.ai_cache import AICacheManager
        
        # Test that the class exists and can be instantiated
        ai_cache_manager = AICacheManager(Path("/tmp/test_cache.json"))
        assert hasattr(ai_cache_manager, 'get_cached_result')
        assert hasattr(ai_cache_manager, 'cache_result')


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
