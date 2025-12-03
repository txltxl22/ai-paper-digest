"""
Tests for the decoupled event tracking system.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from app.event_tracking.event_tracker import EventTracker
from app.event_tracking.event_types import EventType
from app.event_tracking.models import Event, EventPayload


class TestEventTypes:
    """Test event type validation."""
    
    def test_valid_event_types(self):
        """Test that all expected event types are valid."""
        valid_types = [
            "mark_read", "unmark_read", "open_pdf",
            "login", "logout", "reset", "read_list"
        ]
        
        for event_type in valid_types:
            assert EventType.is_valid(event_type)
    
    def test_invalid_event_types(self):
        """Test that invalid event types are rejected."""
        invalid_types = ["invalid", "unknown", "test", ""]
        
        for event_type in invalid_types:
            assert not EventType.is_valid(event_type)
    
    def test_get_allowed_types(self):
        """Test getting all allowed event types."""
        allowed = EventType.get_allowed_types()
        expected = {
            "mark_read", "unmark_read", "open_pdf",
            "login", "logout", "reset", "read_list"
        }
        assert allowed == expected


class TestEventModels:
    """Test event data models."""
    
    def test_event_payload_validation(self):
        """Test EventPayload validation."""
        # Valid payload
        payload = EventPayload(
            type="mark_read",
            arxiv_id="1234.5678",
            meta={"test": "data"},
            ts="2025-01-01T00:00:00Z",
            tz_offset_min=480
        )
        assert payload.validate()
        
        # Invalid payload - wrong type
        payload = EventPayload(
            type=123,  # Should be string
            arxiv_id="1234.5678"
        )
        assert not payload.validate()
    
    def test_event_serialization(self):
        """Test Event serialization to/from dict."""
        event = Event(
            ts="2025-01-01T00:00:00+08:00",
            type="mark_read",
            arxiv_id="1234.5678",
            meta={"test": "data"},
            path="/test",
            ua="test-agent"
        )
        
        # Convert to dict
        event_dict = event.to_dict()
        assert event_dict["ts"] == "2025-01-01T00:00:00+08:00"
        assert event_dict["type"] == "mark_read"
        assert event_dict["arxiv_id"] == "1234.5678"
        assert event_dict["meta"] == {"test": "data"}
        assert event_dict["path"] == "/test"
        assert event_dict["ua"] == "test-agent"
        
        # Convert back from dict
        event_from_dict = Event.from_dict(event_dict)
        assert event_from_dict.ts == event.ts
        assert event_from_dict.type == event.type
        assert event_from_dict.arxiv_id == event.arxiv_id
        assert event_from_dict.meta == event.meta
        assert event_from_dict.path == event.path
        assert event_from_dict.ua == event.ua


class TestEventTracker:
    """Test the main EventTracker class."""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create a temporary directory for testing."""
        return tmp_path / "user_data"
    
    @pytest.fixture
    def tracker(self, temp_dir):
        """Create an EventTracker instance for testing."""
        return EventTracker(temp_dir)
    
    def test_track_valid_event(self, tracker):
        """Test tracking a valid event."""
        success = tracker.track_event(
            uid="test_user",
            event_type="mark_read",
            arxiv_id="1234.5678",
            meta={"test": "data"}
        )
        assert success
        
        # Check that event was saved
        events = tracker.get_user_events("test_user")
        assert len(events) == 1
        assert events[0].type == "mark_read"
        assert events[0].arxiv_id == "1234.5678"
        assert events[0].meta == {"test": "data"}
    
    def test_track_invalid_event(self, tracker):
        """Test tracking an invalid event type."""
        success = tracker.track_event(
            uid="test_user",
            event_type="invalid_type"
        )
        assert not success
        
        # Check that no event was saved
        events = tracker.get_user_events("test_user")
        assert len(events) == 0
    
    def test_process_event_payload(self, tracker):
        """Test processing an event payload."""
        payload = EventPayload(
            type="login",
            ts="2025-01-01T00:00:00Z",
            tz_offset_min=480
        )
        
        success = tracker.process_event_payload("test_user", payload)
        assert success
        
        # Check that event was saved
        events = tracker.get_user_events("test_user")
        assert len(events) == 1
        assert events[0].type == "login"
    
    def test_get_event_stats(self, tracker):
        """Test getting event statistics."""
        # Track multiple events
        tracker.track_event("test_user", "mark_read", "1234.5678")
        tracker.track_event("test_user", "mark_read", "1234.5679")
        tracker.track_event("test_user", "login")
        
        stats = tracker.get_event_stats("test_user")
        assert stats["mark_read"] == 2
        assert stats["login"] == 1
        assert len(stats) == 2
    
    def test_timestamp_parsing(self, tracker):
        """Test client timestamp parsing."""
        # Test with timezone offset
        ts_local = tracker._parse_client_timestamp(
            "2025-01-01T00:00:00Z",
            480  # UTC+8
        )
        assert ts_local is not None
        # The result should be in the local timezone, so we just check it's a valid timestamp
        assert "T" in ts_local and len(ts_local) > 10
        
        # Test without timezone offset
        ts_local = tracker._parse_client_timestamp(
            "2025-01-01T00:00:00Z",
            None
        )
        assert ts_local is not None
        assert "T" in ts_local and len(ts_local) > 10
        
        # Test invalid timestamp
        ts_local = tracker._parse_client_timestamp(
            "invalid-timestamp",
            480
        )
        assert ts_local is None
