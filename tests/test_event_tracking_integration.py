"""
Integration Tests for Event Tracking System

Tests the complete event tracking system including HTTP endpoints,
data persistence, validation, and timezone handling.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path

from app.main import app


class TestEventTrackingIntegration:
    """Integration tests for the event tracking system."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        app.config['TESTING'] = True
        return app.test_client()
    
    @pytest.fixture
    def test_user(self):
        """Create a test user ID."""
        return "integration_test_user"
    
    def _cleanup_user_data(self, test_user: str):
        """Clean up user data file after test."""
        user_data_file = Path("user_data") / f"{test_user}.json"
        if user_data_file.exists():
            user_data_file.unlink()
    
    def _cleanup_all_test_files(self):
        """Clean up all test user files."""
        user_data_dir = Path("user_data")
        for file_path in user_data_dir.glob("*test_user*.json"):
            file_path.unlink()
    
    def test_basic_event_ingestion(self, client):
        """Test basic event ingestion with valid event types."""
        import time
        test_user = f"basic_test_user_{int(time.time())}"
        client.set_cookie('uid', test_user)
        
        try:
            # Test login event
            res1 = client.post('/event', json={
                'type': 'login',
                'ts': '2025-01-01T00:00:00Z',
                'tz_offset_min': 480
            })
            assert res1.status_code == 200
            assert res1.get_json()['status'] == 'ok'
            
            # Test mark_read event
            res2 = client.post('/event', json={
                'type': 'mark_read',
                'arxiv_id': '1234.5678',
                'ts': '2025-01-01T00:00:00Z',
                'tz_offset_min': 480
            })
            assert res2.status_code == 200
            assert res2.get_json()['status'] == 'ok'
            
            # Verify events were saved
            res3 = client.get('/events')
            assert res3.status_code == 200
            events = res3.get_json()['events']
            assert len(events) == 2
            
            event_types = [e['type'] for e in events]
            assert 'login' in event_types
            assert 'mark_read' in event_types
        finally:
            # Clean up test data
            self._cleanup_user_data(test_user)
    
    def test_event_validation_and_filtering(self, client):
        """Test that invalid events are filtered out but return 200."""
        import time
        test_user = f"validation_test_user_{int(time.time())}"
        client.set_cookie('uid', test_user)
        
        try:
            # Test invalid event type
            res1 = client.post('/event', json={
                'type': 'invalid_event_type',
                'ts': '2025-01-01T00:00:00Z'
            })
            assert res1.status_code == 200  # Should return 200 for backward compatibility
            assert res1.get_json()['status'] == 'ok'
            
            # Test missing UID (should return 400)
            client.delete_cookie('uid')
            res2 = client.post('/event', json={
                'type': 'login',
                'ts': '2025-01-01T00:00:00Z'
            })
            assert res2.status_code == 400  # Should return 400 for missing UID
            assert 'error' in res2.get_json()
            
            # Verify only valid events were saved
            client.set_cookie('uid', test_user)
            res3 = client.get('/events')
            events = res3.get_json()['events']
            assert len(events) == 0  # Invalid event should not be saved
        finally:
            # Clean up test data
            self._cleanup_user_data(test_user)
    
    def test_timezone_conversion(self, client):
        """Test timezone conversion for different offsets."""
        import time
        test_user = f"timezone_test_user_{int(time.time())}"
        client.set_cookie('uid', test_user)
        
        try:
            # Test different timezone offsets
            test_cases = [
                {'offset': 480, 'desc': 'UTC+8'},
                {'offset': -300, 'desc': 'UTC-5'},
                {'offset': 0, 'desc': 'UTC'},
                {'offset': 60, 'desc': 'UTC+1'}
            ]
            
            for case in test_cases:
                res = client.post('/event', json={
                    'type': 'login',
                    'ts': '2025-01-01T12:00:00Z',
                    'tz_offset_min': case['offset']
                })
                assert res.status_code == 200
            
            # Get all events and verify timezone conversion
            res = client.get('/events')
            events = res.get_json()['events']
            assert len(events) == 4
            
            # Check that timestamps have timezone offsets
            for event in events:
                ts = event['ts']
                assert 'T' in ts  # ISO format
                assert '+' in ts or '-' in ts[10:]  # Has timezone offset
        finally:
            # Clean up test data
            self._cleanup_user_data(test_user)
    
    def test_event_statistics(self, client):
        """Test event statistics generation."""
        import time
        test_user = f"stats_test_user_{int(time.time())}"
        client.set_cookie('uid', test_user)
        
        try:
            # Send multiple events of different types
            events_to_send = [
                {'type': 'login'},
                {'type': 'mark_read', 'arxiv_id': '1234.5678'},
                {'type': 'mark_read', 'arxiv_id': '1234.5679'},
                {'type': 'open_pdf', 'arxiv_id': '1234.5680'},
                {'type': 'logout'}
            ]
            
            for event_data in events_to_send:
                res = client.post('/event', json=event_data)
                assert res.status_code == 200
            
            # Get statistics
            res = client.get('/events/stats')
            assert res.status_code == 200
            stats = res.get_json()['stats']
            
            # Verify statistics
            assert stats['login'] == 1
            assert stats['mark_read'] == 2
            assert stats['open_pdf'] == 1
            assert stats['logout'] == 1
            assert len(stats) == 4
        finally:
            # Clean up test data
            self._cleanup_user_data(test_user)
    
    def test_event_metadata_handling(self, client):
        """Test handling of event metadata."""
        import time
        test_user = f"metadata_test_user_{int(time.time())}"
        client.set_cookie('uid', test_user)
        
        try:
            # Test event with complex metadata
            complex_metadata = {
                'href': 'https://arxiv.org/pdf/1234.5678.pdf',
                'user_agent': 'test-browser',
                'page': 'index',
                'custom_field': 'custom_value'
            }
            
            res = client.post('/event', json={
                'type': 'open_pdf',
                'arxiv_id': '1234.5678',
                'meta': complex_metadata,
                'ts': '2025-01-01T00:00:00Z',
                'tz_offset_min': 480
            })
            assert res.status_code == 200
            
            # Verify metadata was saved correctly
            res = client.get('/events')
            events = res.get_json()['events']
            assert len(events) == 1
            
            event = events[0]
            assert event['type'] == 'open_pdf'
            assert event['arxiv_id'] == '1234.5678'
            assert event['meta'] == complex_metadata
        finally:
            # Clean up test data
            self._cleanup_user_data(test_user)
    
    def test_browser_simulation(self, client):
        """Test browser-like requests with proper headers."""
        import time
        test_user = f"browser_test_user_{int(time.time())}"
        client.set_cookie('uid', test_user)
        
        try:
            # Simulate browser request with headers
            res = client.post('/event', 
                json={
                    'type': 'open_pdf',
                    'arxiv_id': '9999.8888',
                    'meta': {'href': 'https://arxiv.org/pdf/9999.8888.pdf'},
                    'ts': '2025-01-01T15:30:00Z',
                    'tz_offset_min': 480
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Referer': 'http://localhost:22581/',
                    'Accept': 'application/json'
                }
            )
            assert res.status_code == 200
            
            # Verify browser metadata was captured
            res = client.get('/events')
            events = res.get_json()['events']
            assert len(events) == 1
            
            event = events[0]
            assert event['type'] == 'open_pdf'
            assert event['arxiv_id'] == '9999.8888'
            assert event['meta']['href'] == 'https://arxiv.org/pdf/9999.8888.pdf'
            assert 'Mozilla' in event['ua']  # User agent captured
            assert event['path'] == '/event'  # Path captured
        finally:
            # Clean up test data
            self._cleanup_user_data(test_user)
    
    def test_all_event_types(self, client):
        """Test all supported event types."""
        import time
        test_user = f"all_events_test_user_{int(time.time())}"
        client.set_cookie('uid', test_user)
        
        try:
            # All supported event types
            event_types = [
                'login', 'logout', 'mark_read', 'unmark_read', 
                'open_pdf', 'read_list', 'reset'
            ]
            
            # Send one event of each type
            for i, event_type in enumerate(event_types):
                payload = {'type': event_type}
                
                # Add arxiv_id for paper-related events
                if event_type in ['mark_read', 'unmark_read', 'open_pdf']:
                    payload['arxiv_id'] = f'1234.{5000 + i}'
                
                # Add metadata for specific events
                if event_type == 'open_pdf':
                    payload['meta'] = {'href': f'https://arxiv.org/pdf/1234.{5000 + i}.pdf'}
                
                res = client.post('/event', json=payload)
                assert res.status_code == 200
            
            # Verify all events were saved
            res = client.get('/events')
            events = res.get_json()['events']
            assert len(events) == 7
            
            # Check event types
            saved_types = [e['type'] for e in events]
            for event_type in event_types:
                assert event_type in saved_types
        finally:
            # Clean up test data
            self._cleanup_user_data(test_user)
    
    def test_error_handling_and_edge_cases(self, client):
        """Test error handling and edge cases."""
        import time
        test_user = f"error_test_user_{int(time.time())}"
        client.set_cookie('uid', test_user)
        
        try:
            # Test invalid event type (should be filtered out)
            res1 = client.post('/event', json={'type': 'invalid_event_type'})
            assert res1.status_code == 200
            
            # Test valid event type (should be saved)
            res2 = client.post('/event', json={'type': 'login'})
            assert res2.status_code == 200
            
            # Test another invalid event type
            res3 = client.post('/event', json={'type': 'unknown_event'})
            assert res3.status_code == 200
            
            # Verify only valid events were saved
            res = client.get('/events')
            events = res.get_json()['events']
            
            # Should have only 1 event (the login event)
            assert len(events) == 1
            
            # Check that invalid event types were filtered out
            event_types = [e['type'] for e in events]
            assert 'invalid_event_type' not in event_types
            assert 'unknown_event' not in event_types
            assert 'login' in event_types
        finally:
            # Clean up test data
            self._cleanup_user_data(test_user)
