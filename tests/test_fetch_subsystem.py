"""
Tests for the fetch subsystem.
"""
import pytest
import json
from pathlib import Path
from app.fetch.models import FetchCommand, FetchResult, StreamEvent
from app.fetch.services import FetchService


class TestFetchSubsystem:
    """Test the fetch subsystem functionality."""
    
    def test_fetch_command_building(self, tmp_path):
        """Test that fetch commands are built correctly."""
        service = FetchService(tmp_path)
        
        # Test with default feed URL
        cmd = service.build_fetch_command()
        assert isinstance(cmd, FetchCommand)
        assert cmd.feed_url == "https://papers.takara.ai/api/feed"
        assert cmd.timeout == 300
        assert cmd.working_directory == str(tmp_path)
        assert "feed_paper_summarizer_service.py" in cmd.command
        
        # Test with custom feed URL
        cmd2 = service.build_fetch_command("https://custom.feed.url")
        assert cmd2.feed_url == "https://custom.feed.url"
    
    def test_fetch_result_creation(self):
        """Test FetchResult creation and properties."""
        result = FetchResult(
            success=True,
            return_code=0,
            stdout="Found 5 papers",
            stderr="",
            summary_stats={"papers_found": "Found 5 papers"}
        )
        
        assert result.success is True
        assert result.return_code == 0
        assert "Found 5 papers" in result.stdout
        assert result.summary_stats["papers_found"] == "Found 5 papers"
    
    def test_stream_event_creation(self):
        """Test StreamEvent creation and properties."""
        event = StreamEvent(
            event_type="status",
            message="正在启动服务...",
            icon="⏳",
            level="info"
        )
        
        assert event.event_type == "status"
        assert event.message == "正在启动服务..."
        assert event.icon == "⏳"
        assert event.level == "info"
    
    def test_summary_stats_extraction(self, tmp_path):
        """Test that summary statistics are extracted correctly from output."""
        service = FetchService(tmp_path)
        
        # Test output with various statistics
        test_output = """
        Found 5 papers in RSS feed
        Successfully processed 3 papers
        RSS feed updated with new summaries
        All done!
        """
        
        stats = service._extract_summary_stats(test_output)
        
        assert "papers_found" in stats
        assert "success_count" in stats
        assert "rss_updated" in stats
        assert "completion" in stats
        
        assert "Found 5 papers" in stats["papers_found"]
        assert "Successfully processed 3 papers" in stats["success_count"]
        assert "RSS feed updated" in stats["rss_updated"]
        assert "All done!" in stats["completion"]
    
    def test_summary_stats_extraction_empty_output(self, tmp_path):
        """Test summary stats extraction with empty output."""
        service = FetchService(tmp_path)
        
        stats = service._extract_summary_stats("")
        assert isinstance(stats, dict)
        assert len(stats) == 0
        
        stats2 = service._extract_summary_stats(None)
        assert isinstance(stats2, dict)
        assert len(stats2) == 0
