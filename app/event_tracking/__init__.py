"""
Event Tracking Subsystem

A decoupled event tracking system for user analytics and behavior monitoring.
"""

from .event_tracker import EventTracker
from .event_types import EventType
from .models import Event, EventPayload

__all__ = ['EventTracker', 'EventType', 'Event', 'EventPayload']
