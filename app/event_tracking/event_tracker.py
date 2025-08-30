"""
Event Tracker

Main class for handling event tracking operations including validation,
processing, and storage.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from flask import request

from .event_types import EventType
from .models import Event, EventPayload


class EventTracker:
    """Main event tracking system."""
    
    def __init__(self, user_data_dir: Path):
        """Initialize the event tracker.
        
        Args:
            user_data_dir: Directory where user data files are stored
        """
        self.user_data_dir = user_data_dir
        self.user_data_dir.mkdir(exist_ok=True)
    
    def _user_file(self, uid: str) -> Path:
        """Get user data file path."""
        return self.user_data_dir / f"{uid}.json"
    
    def _load_user_data(self, uid: str) -> Dict[str, Any]:
        """Load user data with backward compatibility."""
        try:
            data = json.loads(self._user_file(uid).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        # Ensure events list exists
        if "events" not in data:
            data["events"] = []
        
        return data
    
    def _save_user_data(self, uid: str, data: Dict[str, Any]) -> None:
        """Save user data to file."""
        self._user_file(uid).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def _parse_client_timestamp(self, ts_client: str, tz_offset_min: Optional[int]) -> Optional[str]:
        """Parse client timestamp and convert to local timezone.
        
        Args:
            ts_client: ISO 8601 timestamp from client
            tz_offset_min: Timezone offset in minutes (UTC - local)
            
        Returns:
            Local timestamp in ISO format or None if parsing fails
        """
        try:
            # Accept 'Z' by replacing with +00:00
            dt_utc = datetime.fromisoformat(str(ts_client).replace('Z', '+00:00'))
            
            if isinstance(tz_offset_min, int):
                tz = timezone(timedelta(minutes=-tz_offset_min))
                dt_local = dt_utc.astimezone(tz)
                return dt_local.isoformat(timespec="seconds")
            else:
                return dt_utc.astimezone().isoformat(timespec="seconds")
        except Exception:
            return None
    
    def track_event(
        self,
        uid: str,
        event_type: str,
        arxiv_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        ts: Optional[str] = None
    ) -> bool:
        """Track a single event for a user.
        
        Args:
            uid: User identifier
            event_type: Type of event (must be in allowed types)
            arxiv_id: Optional arXiv ID for paper-related events
            meta: Optional metadata dictionary
            ts: Optional timestamp (if not provided, uses current time)
            
        Returns:
            True if event was tracked successfully, False otherwise
        """
        # Validate event type
        if not EventType.is_valid(event_type):
            return False
        
        # Load user data
        data = self._load_user_data(uid)
        
        # Create event
        event = Event(
            ts=ts or datetime.now().astimezone().isoformat(timespec="seconds"),
            type=event_type,
            arxiv_id=arxiv_id,
            meta=meta or {},
            path=request.path if request else None,
            ua=request.headers.get("User-Agent") if request else None
        )
        
        # Append to events list
        data["events"].append(event.to_dict())
        
        # Save user data
        self._save_user_data(uid, data)
        
        return True
    
    def process_event_payload(self, uid: str, payload: EventPayload) -> bool:
        """Process an event payload from the frontend.
        
        Args:
            uid: User identifier
            payload: Event payload from frontend
            
        Returns:
            True if event was processed successfully, False otherwise
        """
        # Validate payload
        if not payload.validate():
            return False
        
        # Validate event type
        if not EventType.is_valid(payload.type):
            return False
        
        # Parse timestamp
        ts_local = None
        if payload.ts:
            ts_local = self._parse_client_timestamp(payload.ts, payload.tz_offset_min)
        
        # Track the event
        return self.track_event(
            uid=uid,
            event_type=payload.type,
            arxiv_id=payload.arxiv_id,
            meta=payload.meta,
            ts=ts_local
        )
    
    def get_user_events(self, uid: str, limit: Optional[int] = None) -> List[Event]:
        """Get events for a user.
        
        Args:
            uid: User identifier
            limit: Optional limit on number of events to return
            
        Returns:
            List of Event objects
        """
        data = self._load_user_data(uid)
        events = data.get("events", [])
        
        # Convert to Event objects
        event_objects = [Event.from_dict(e) for e in events]
        
        # Apply limit if specified
        if limit is not None:
            event_objects = event_objects[-limit:]  # Get most recent events
        
        return event_objects
    
    def get_event_stats(self, uid: str) -> Dict[str, int]:
        """Get event statistics for a user.
        
        Args:
            uid: User identifier
            
        Returns:
            Dictionary with event type counts
        """
        events = self.get_user_events(uid)
        stats = {}
        
        for event in events:
            event_type = event.type
            stats[event_type] = stats.get(event_type, 0) + 1
        
        return stats
