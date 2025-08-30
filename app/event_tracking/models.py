"""
Data Models for Event Tracking

Defines the data structures used by the event tracking system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class EventPayload:
    """Payload structure for incoming events from frontend."""
    
    type: str
    arxiv_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    ts: Optional[str] = None
    tz_offset_min: Optional[int] = None
    
    def validate(self) -> bool:
        """Validate the payload structure."""
        return (
            isinstance(self.type, str) and
            (self.arxiv_id is None or isinstance(self.arxiv_id, str)) and
            isinstance(self.meta, dict) and
            (self.ts is None or isinstance(self.ts, str)) and
            (self.tz_offset_min is None or isinstance(self.tz_offset_min, int))
        )


@dataclass
class Event:
    """Internal event structure for storage."""
    
    ts: str
    type: str
    arxiv_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None
    ua: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ts": self.ts,
            "type": self.type,
            "arxiv_id": self.arxiv_id,
            "meta": self.meta,
            "path": self.path,
            "ua": self.ua
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create Event from dictionary."""
        return cls(
            ts=data.get("ts", ""),
            type=data.get("type", ""),
            arxiv_id=data.get("arxiv_id"),
            meta=data.get("meta", {}),
            path=data.get("path"),
            ua=data.get("ua")
        )
