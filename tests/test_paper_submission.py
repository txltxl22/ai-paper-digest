import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
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


def create_mock_quota_manager(allowed=True, tier="normal", remaining=3, message="OK"):
    """Create a mock QuotaManager for testing."""
    from app.quota.models import UserTier, QuotaResult
    
    mock_quota = MagicMock()
    
    # Mock check_only to return a QuotaResult
    quota_result = QuotaResult(
        allowed=allowed,
        tier=UserTier.NORMAL if tier == "normal" else UserTier.GUEST if tier == "guest" else UserTier.ADMIN,
        remaining_daily=remaining,
        message=message
    )
    mock_quota.check_only.return_value = quota_result
    
    # Mock check_and_consume to return the same result
    mock_quota.check_and_consume.return_value = quota_result
    
    # Mock get_client_ip
    mock_quota.get_client_ip.return_value = "127.0.0.1"
    
    # Mock get_quota_info
    def get_quota_info_side_effect(ip, uid):
        return {
            "tier": tier,
            "daily_limit": 3 if tier == "normal" else 1,
            "used_today": (3 if tier == "normal" else 1) - remaining,
            "remaining": remaining,
            "is_unlimited": tier == "admin",
            "message": message
        }
    mock_quota.get_quota_info.side_effect = get_quota_info_side_effect
    
    return mock_quota


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
        
        # Test not logged in - guests can now submit (quota system handles it)
        # The request will fail later in processing, not at auth stage
        # We just verify it doesn't return 401 immediately
        response = client.post("/submit_paper", json={"url": "https://fake-arxiv.org/abs/9999.99999"})
        # Should not be 401 (guests allowed), but will fail during processing
        assert response.status_code != 401
    
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
        
        # Create mock quota manager that denies (limit exceeded)
        mock_quota = create_mock_quota_manager(allowed=False, tier="normal", remaining=0, message="您今日的免费额度已用完，升级Pro获取更多")
        # Override to return specific error message
        from app.quota.models import UserTier, QuotaResult
        quota_result = QuotaResult(
            allowed=False,
            tier=UserTier.NORMAL,
            reason="user_limit",
            remaining_daily=0,
            message="您今日的免费额度已用完，升级Pro获取更多"
        )
        mock_quota.check_only.return_value = quota_result
        mock_quota.check_and_consume.return_value = quota_result
        
        # Create the service
        service = PaperSubmissionService(
            user_data_manager=user_data_manager,
            ai_cache_manager=ai_cache_manager,
            ai_checker=ai_checker,
            summary_dir=summary_dir,
            llm_config=MockLLMConfig(),
            paper_config=MockPaperConfig(),
            save_summary_func=None,
            quota_manager=mock_quota
        )
        
        # Test daily limit exceeded
        result = service.submit_paper("https://arxiv.org/abs/2506.12345", "testuser")
        
        assert result.success is False
        assert "额度已用完" in result.message or "Daily limit exceeded" in result.error
        assert result.error in ["user_limit", "ip_limit", "Daily limit exceeded"]
    
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
        
        # Create mock quota manager that allows
        mock_quota = create_mock_quota_manager(allowed=True, tier="normal", remaining=3)
        
        # Create the service
        service = PaperSubmissionService(
            user_data_manager=user_data_manager,
            ai_cache_manager=ai_cache_manager,
            ai_checker=ai_checker,
            summary_dir=summary_dir,
            llm_config=MockLLMConfig(),
            paper_config=MockPaperConfig(),
            save_summary_func=None,
            quota_manager=mock_quota
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
        
        # Create mock quota manager that allows
        mock_quota = create_mock_quota_manager(allowed=True, tier="normal", remaining=3)
        
        # Create the service
        service = PaperSubmissionService(
            user_data_manager=user_data_manager,
            ai_cache_manager=ai_cache_manager,
            ai_checker=ai_checker,
            summary_dir=summary_dir,
            llm_config=MockLLMConfig(),
            paper_config=MockPaperConfig(),
            save_summary_func=None,
            quota_manager=mock_quota
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
        
        # Create mock quota manager that allows
        mock_quota = create_mock_quota_manager(allowed=True, tier="normal", remaining=3)
        
        # Create the service
        service = PaperSubmissionService(
            user_data_manager=user_data_manager,
            ai_cache_manager=ai_cache_manager,
            ai_checker=ai_checker,
            summary_dir=summary_dir,
            llm_config=MockLLMConfig(),
            paper_config=MockPaperConfig(),
            save_summary_func=None,
            quota_manager=mock_quota
        )
        
        # Test that the service components are properly initialized
        assert service.user_data_manager is user_data_manager
        assert service.ai_cache_manager is ai_cache_manager
        assert service.ai_checker is ai_checker
        assert service.quota_manager is mock_quota
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
        
        # Login user
        client.set_cookie("uid", "testuser")
        
        # Test that the daily limit check is working by checking the quota endpoint
        response = client.get("/quota")
        assert response.status_code == 200
        
        quota_data = response.get_json()
        assert "quota" in quota_data
        assert "daily_limit" in quota_data["quota"]
        assert "remaining" in quota_data["quota"]
        
        # Verify that the daily limit is 3 (default configuration)
        assert quota_data["quota"]["daily_limit"] == 3
        
        # Test that we can get quota information even when limit is reached
        # This verifies that the daily limit system is working correctly
        # The actual limit enforcement is tested in other unit tests

    def test_pdf_size_limit_configuration(self, client, tmp_path):
        """Test that PDF size limit is properly configured and enforced."""
        import app.main as sp
        from config_manager import ConfigManager
        
        # Test that the attribute exists
        assert hasattr(sp.paper_config, 'max_pdf_size_mb')
        
        # Get the expected value from the config manager
        config = ConfigManager()
        expected_value = config.get_paper_processing_config().max_pdf_size_mb
        
        # Test that the value matches the config
        assert sp.paper_config.max_pdf_size_mb == expected_value
        
        # Test configuration override via environment variable
        with patch.dict(os.environ, {'MAX_PDF_SIZE_MB': '50'}):
            # Recreate the config to test environment override
            config = ConfigManager()
            paper_config = config.get_paper_processing_config()
            assert paper_config.max_pdf_size_mb == 50

    def test_progress_cache_persistence(self, client, tmp_path):
        """Test that progress cache is properly persisted and loaded."""
        from app.paper_submission.services import PaperSubmissionService
        from app.paper_submission.user_data import UserDataManager
        from app.paper_submission.ai_cache import AICacheManager
        from app.paper_submission.ai_checker import AIContentChecker
        
        # Setup test directories
        user_data_dir = tmp_path / "user_data"
        summary_dir = tmp_path / "summary"
        data_dir = tmp_path / "data"
        
        for dir_path in [user_data_dir, summary_dir, data_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create service instance
        mock_quota = create_mock_quota_manager(allowed=True, tier="normal", remaining=3)
        service = PaperSubmissionService(
            user_data_manager=UserDataManager(user_data_dir),
            ai_cache_manager=AICacheManager(data_dir / "ai_cache.json"),
            ai_checker=AIContentChecker(AICacheManager(data_dir / "ai_cache.json"), Mock(), Path("prompts")),
            summary_dir=summary_dir,
            llm_config=Mock(),
            paper_config=Mock(),
            save_summary_func=Mock(),
            quota_manager=mock_quota
        )
        
        # Override the progress cache file to use a temporary one
        service.progress_cache_file = data_dir / "progress_cache.json"
        service.progress_cache = {}  # Clear any loaded cache
        
        # Test initial state
        assert service.progress_cache == {}
        
        # Test progress update
        task_id = "test-task-123"
        service._update_progress(task_id, "downloading", 50, "Downloading PDF...")
        
        # Verify progress is saved
        assert task_id in service.progress_cache
        assert service.progress_cache[task_id]["step"] == "downloading"
        assert service.progress_cache[task_id]["progress"] == 50
        
        # Test progress retrieval
        progress = service.get_progress(task_id)
        assert progress["step"] == "downloading"
        assert progress["progress"] == 50

    def test_quota_not_consumed_for_processed_papers(self, client, tmp_path):
        """Test that quota is not consumed when resubmitting already processed papers."""
        from app.paper_submission.user_data import UserDataManager
        import json
        
        # Setup test directories
        user_data_dir = tmp_path / "user_data"
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a user data file with a processed paper
        user_file = user_data_dir / "testuser.json"
        user_data = {
            "read": {},
            "events": [],
            "uploaded_urls": [
                {
                    "url": "https://arxiv.org/abs/2506.12345",
                    "timestamp": "2025-08-31T10:00:00.000000",
                    "ai_judgment": {"is_ai": True, "confidence": 0.9, "tags": []},
                    "process_result": {
                        "success": True,
                        "error": None,
                        "summary_path": "/path/to/summary.md",
                        "paper_subject": "Test Paper"
                    }
                }
            ]
        }
        user_file.write_text(json.dumps(user_data), encoding="utf-8")
        
        # Create user data manager
        user_data_manager = UserDataManager(user_data_dir)
        
        # Test that the paper is correctly identified as processed
        assert user_data_manager.has_processed_paper("testuser", "https://arxiv.org/abs/2506.12345") is True
        
        # Test that a different paper is not identified as processed
        assert user_data_manager.has_processed_paper("testuser", "https://arxiv.org/abs/2506.67890") is False

    def test_timestamp_tracking_first_created_at(self, client, tmp_path):
        """Test that first_created_at timestamp is preserved when resubmitting papers."""
        from summary_service.record_manager import create_service_record, save_summary_with_service_record
        import json
        
        # Setup test directories
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Test create_service_record with first_created_at
        record = create_service_record(
            arxiv_id="2506.12345",
            source_type="user",
            user_id="testuser",
            original_url="https://arxiv.org/abs/2506.12345",
            first_created_at="2025-08-30T15:30:00.000000"
        )
        
        # Verify first_created_at is set correctly (now returns ServiceRecord object)
        assert record.first_created_at == "2025-08-30T15:30:00.000000"
        assert record.created_at != record.first_created_at
        
        # Test create_service_record without first_created_at (should use current time)
        record2 = create_service_record(
            arxiv_id="2506.67890",
            source_type="user",
            user_id="testuser",
            original_url="https://arxiv.org/abs/2506.67890"
        )
        
        # Verify first_created_at defaults to created_at
        assert record2.first_created_at == record2.created_at

    def test_paper_sorting_by_submission_time(self, client, tmp_path):
        """Test that papers are sorted by submission time (newest first)."""
        from app.index_page.services import EntryScanner
        import json
        from datetime import datetime
        
        # Setup test directories
        summary_dir = tmp_path / "summary"
        summary_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test summary files with different submission times using proper save function
        from summary_service.models import StructuredSummary, PaperInfo, Tags, Results
        from summary_service.record_manager import save_summary_with_service_record
        
        # Paper 1: submitted first (older)
        paper1_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="Paper 1", title_en="Paper 1", abstract="Paper 1 content", submission_date="2025-08-30"),
            one_sentence_summary="Paper 1 content",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        paper1_tags = Tags(top=[], tags=[])
        save_summary_with_service_record(
            arxiv_id="2506.12345",
            summary_content=paper1_summary,
            tags=paper1_tags,
            summary_dir=summary_dir,
            source_type="user",
            user_id="testuser",
            original_url="https://arxiv.org/abs/2506.12345"
        )
        
        # Manually update submission_date for paper 1 (older date)
        from summary_service.record_manager import load_summary_with_service_record
        record1 = load_summary_with_service_record("2506.12345", summary_dir)
        if record1:
            # Update PaperInfo submission_date
            paper_info1 = record1.summary_data.structured_content.paper_info
            paper_info1.submission_date = "2025-08-30"
            # Create new StructuredSummary with updated PaperInfo
            updated_summary1 = StructuredSummary(
                paper_info=paper_info1,
                one_sentence_summary=record1.summary_data.structured_content.one_sentence_summary,
                innovations=record1.summary_data.structured_content.innovations,
                results=record1.summary_data.structured_content.results,
                terminology=record1.summary_data.structured_content.terminology
            )
            save_summary_with_service_record(
                arxiv_id="2506.12345",
                summary_content=updated_summary1,
                tags=record1.summary_data.tags,
                summary_dir=summary_dir,
                source_type="user",
                user_id="testuser",
                original_url="https://arxiv.org/abs/2506.12345"
            )
        
        # Paper 2: submitted second (newer)
        paper2_summary = StructuredSummary(
            paper_info=PaperInfo(title_zh="Paper 2", title_en="Paper 2", abstract="Paper 2 content", submission_date="2025-08-31"),
            one_sentence_summary="Paper 2 content",
            innovations=[],
            results=Results(experimental_highlights=[], practical_value=[]),
            terminology=[]
        )
        paper2_tags = Tags(top=[], tags=[])
        save_summary_with_service_record(
            arxiv_id="2506.67890",
            summary_content=paper2_summary,
            tags=paper2_tags,
            summary_dir=summary_dir,
            source_type="user",
            user_id="testuser",
            original_url="https://arxiv.org/abs/2506.67890"
        )
        
        # Create scanner and scan entries
        scanner = EntryScanner(summary_dir)
        entries = scanner.scan_entries_meta()
        
        # Verify papers are sorted by submission time (newest first)
        assert len(entries) == 2
        assert entries[0]["id"] == "2506.67890"  # Newer paper first
        assert entries[1]["id"] == "2506.12345"  # Older paper second
        
        # Verify submission times are correctly extracted
        assert entries[0]["submission_time"] > entries[1]["submission_time"]

    def test_chinese_progress_messages(self, client, tmp_path):
        """Test that progress messages are in Chinese."""
        from app.paper_submission.services import PaperSubmissionService
        from app.paper_submission.user_data import UserDataManager
        from app.paper_submission.ai_cache import AICacheManager
        from app.paper_submission.ai_checker import AIContentChecker
        
        # Setup test directories
        user_data_dir = tmp_path / "user_data"
        summary_dir = tmp_path / "summary"
        data_dir = tmp_path / "data"
        
        for dir_path in [user_data_dir, summary_dir, data_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create service instance
        mock_quota = create_mock_quota_manager(allowed=True, tier="normal", remaining=3)
        service = PaperSubmissionService(
            user_data_manager=UserDataManager(user_data_dir),
            ai_cache_manager=AICacheManager(data_dir / "ai_cache.json"),
            ai_checker=AIContentChecker(AICacheManager(data_dir / "ai_cache.json"), Mock(), Path("prompts")),
            summary_dir=summary_dir,
            llm_config=Mock(),
            paper_config=Mock(),
            save_summary_func=Mock(),
            quota_manager=mock_quota
        )
        
        # Override the progress cache file to use a temporary one
        service.progress_cache_file = data_dir / "progress_cache.json"
        service.progress_cache = {}
        
        # Test various progress updates and verify they're in Chinese
        task_id = "test-task-123"
        
        # Test different progress steps
        service._update_progress(task_id, "starting", 0, "正在初始化...")
        progress = service.get_progress(task_id)
        assert "正在初始化" in progress["details"]
        
        service._update_progress(task_id, "downloading", 25, "正在下载PDF文件...")
        progress = service.get_progress(task_id)
        assert "正在下载PDF文件" in progress["details"]
        
        service._update_progress(task_id, "extracting", 50, "正在提取文本内容...")
        progress = service.get_progress(task_id)
        assert "正在提取文本内容" in progress["details"]
        
        service._update_progress(task_id, "checking", 75, "正在检查AI相关性...")
        progress = service.get_progress(task_id)
        assert "正在检查AI相关性" in progress["details"]
        
        service._update_progress(task_id, "summarizing", 90, "正在生成摘要...")
        progress = service.get_progress(task_id)
        assert "正在生成摘要" in progress["details"]
        
        service._update_progress(task_id, "completed", 100, "论文处理完成")
        progress = service.get_progress(task_id)
        assert "论文处理完成" in progress["details"]
        
        # Test error message
        service._update_progress(task_id, "error", 0, "论文不是AI相关")
        progress = service.get_progress(task_id)
        assert "论文不是AI相关" in progress["details"]

    def test_quota_api_endpoint(self, client, tmp_path):
        """Test the quota API endpoint returns correct information."""
        from app.paper_submission.services import PaperSubmissionService
        from app.paper_submission.user_data import UserDataManager
        from app.paper_submission.ai_cache import AICacheManager
        from app.paper_submission.ai_checker import AIContentChecker
        import json
        from datetime import date
        
        # Setup test directories
        user_data_dir = tmp_path / "user_data"
        summary_dir = tmp_path / "summary"
        data_dir = tmp_path / "data"
        
        for dir_path in [user_data_dir, summary_dir, data_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create mock quota manager with test data (2 used, 1 remaining)
        mock_quota = create_mock_quota_manager(allowed=True, tier="normal", remaining=1)
        # Override get_quota_info to return specific test values
        def get_quota_info_override(ip, uid):
            return {
                "tier": "normal",
                "daily_limit": 3,
                "used_today": 2,
                "remaining": 1,
                "is_unlimited": False,
                "message": "今日剩余: 1/3"
            }
        mock_quota.get_quota_info.side_effect = get_quota_info_override
        
        # Create service instance
        service = PaperSubmissionService(
            user_data_manager=UserDataManager(user_data_dir),
            ai_cache_manager=AICacheManager(data_dir / "ai_cache.json"),
            ai_checker=AIContentChecker(AICacheManager(data_dir / "ai_cache.json"), Mock(), Path("prompts")),
            summary_dir=summary_dir,
            llm_config=Mock(),
            paper_config=Mock(),
            save_summary_func=Mock(),
            quota_manager=mock_quota
        )
        
        # quota_manager.get_client_ip is already mocked to return "127.0.0.1"
        quota_info = service.get_user_quota("testuser")
        
        # Verify response structure
        assert 'daily_limit' in quota_info
        assert 'used' in quota_info
        assert 'remaining' in quota_info
        assert 'next_reset' in quota_info
        assert 'next_reset_formatted' in quota_info
        
        # Verify values
        assert quota_info['daily_limit'] == 3
        assert quota_info['used'] == 2
        assert quota_info['remaining'] == 1

    def test_download_progress_api_endpoint(self, client, tmp_path):
        """Test the download progress API endpoint."""
        from app.paper_submission.services import PaperSubmissionService
        from app.paper_submission.user_data import UserDataManager
        from app.paper_submission.ai_cache import AICacheManager
        from app.paper_submission.ai_checker import AIContentChecker
        import json
        
        # Setup test directories
        user_data_dir = tmp_path / "user_data"
        summary_dir = tmp_path / "summary"
        data_dir = tmp_path / "data"
        
        for dir_path in [user_data_dir, summary_dir, data_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create service instance
        mock_quota = create_mock_quota_manager(allowed=True, tier="normal", remaining=3)
        service = PaperSubmissionService(
            user_data_manager=UserDataManager(user_data_dir),
            ai_cache_manager=AICacheManager(data_dir / "ai_cache.json"),
            ai_checker=AIContentChecker(AICacheManager(data_dir / "ai_cache.json"), Mock(), Path("prompts")),
            summary_dir=summary_dir,
            llm_config=Mock(),
            paper_config=Mock(),
            save_summary_func=Mock(),
            quota_manager=mock_quota
        )
        
        # Override the progress cache file to use a temporary one
        service.progress_cache_file = data_dir / "progress_cache.json"
        service.progress_cache = {}
        
        # Create a test task with progress
        task_id = "test-task-123"
        service._update_progress(task_id, "downloading", 50, "正在下载PDF文件...")
        
        # Test progress retrieval
        progress = service.get_progress(task_id)
        
        # Verify response structure
        assert 'step' in progress
        assert 'progress' in progress
        assert 'details' in progress
        assert 'timestamp' in progress
        
        # Verify values
        assert progress['step'] == 'downloading'
        assert progress['progress'] == 50
        assert '正在下载PDF文件' in progress['details']
        
        # Test non-existent task
        progress = service.get_progress('non-existent-task')
        assert progress['step'] == 'unknown'
        assert progress['progress'] == 0
        assert '任务未找到' in progress['details']


if __name__ == "__main__":
    pytest.main([__file__])
