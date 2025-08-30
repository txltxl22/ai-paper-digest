"""
Event Types for the Event Tracking System

Defines all allowed event types as an enum for type safety and consistency.
"""

from enum import Enum


class EventType(Enum):
    """Allowed event types for tracking."""
    
    # Article-related events
    MARK_READ = "mark_read"
    UNMARK_READ = "unmark_read"
    READ_MORE = "read_more"
    OPEN_PDF = "open_pdf"
    
    # User session events
    LOGIN = "login"
    LOGOUT = "logout"
    RESET = "reset"
    
    # Navigation events
    READ_LIST = "read_list"
    
    @classmethod
    def is_valid(cls, event_type: str) -> bool:
        """Check if an event type string is valid."""
        try:
            cls(event_type)
            return True
        except ValueError:
            return False
    
    @classmethod
    def get_allowed_types(cls) -> set[str]:
        """Get all allowed event type strings."""
        return {e.value for e in cls}
