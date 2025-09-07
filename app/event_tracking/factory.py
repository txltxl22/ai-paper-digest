"""
Factory for creating event tracking module.
"""
from pathlib import Path
from .routes import create_event_tracking_blueprint
from .event_tracker import EventTracker


def create_event_tracking_module(user_data_dir: Path) -> dict:
    """Create event tracking module with service and routes.
    
    Args:
        user_data_dir: Directory to store event tracking data files
    
    Returns:
        Dictionary containing the service and blueprint
    """
    # Create event tracker service
    event_tracker = EventTracker(user_data_dir)
    
    # Create routes
    blueprint = create_event_tracking_blueprint(user_data_dir)
    
    return {
        "service": event_tracker,
        "blueprint": blueprint
    }
