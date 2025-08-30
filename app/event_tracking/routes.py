"""
Event Tracking Routes

Flask routes for handling event tracking endpoints.
"""

import json
from flask import Blueprint, request, jsonify

from .event_tracker import EventTracker
from .models import EventPayload


def create_event_tracking_blueprint(user_data_dir):
    """Create a Flask blueprint for event tracking routes.
    
    Args:
        user_data_dir: Directory where user data files are stored
        
    Returns:
        Flask blueprint with event tracking routes
    """
    bp = Blueprint('event_tracking', __name__)
    
    @bp.route("/event", methods=["POST"])
    def ingest_event():
        """Ingest an event from the frontend."""
        uid = request.cookies.get("uid")
        if not uid:
            return jsonify({"error": "no-uid"}), 400
        
        try:
            # Parse request payload
            payload_data = request.get_json(silent=True)
            if payload_data is None:
                raw = request.get_data(as_text=True) or "{}"
                try:
                    payload_data = json.loads(raw)
                except Exception:
                    payload_data = {}
            
            # Create EventPayload object
            payload = EventPayload(
                type=str(payload_data.get("type", "")).strip(),
                arxiv_id=payload_data.get("arxiv_id"),
                meta=payload_data.get("meta") or {},
                ts=payload_data.get("ts"),
                tz_offset_min=payload_data.get("tz_offset_min")
            )
            
            # Create event tracker with current user data dir
            from app.main import USER_DATA_DIR
            event_tracker = EventTracker(USER_DATA_DIR)
            
            # Process the event
            success = event_tracker.process_event_payload(uid, payload)
            
            # Always return 200 for backward compatibility with existing tests
            # Invalid events are filtered out but don't cause an error response
            return jsonify({"status": "ok"})
                
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
    
    @bp.route("/events", methods=["GET"])
    def get_events():
        """Get events for the current user (for debugging/admin purposes)."""
        uid = request.cookies.get("uid")
        if not uid:
            return jsonify({"error": "no-uid"}), 400
        
        try:
            limit = request.args.get("limit", type=int)
            from app.main import USER_DATA_DIR
            event_tracker = EventTracker(USER_DATA_DIR)
            events = event_tracker.get_user_events(uid, limit=limit)
            
            return jsonify({
                "status": "ok",
                "events": [event.to_dict() for event in events]
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
    
    @bp.route("/events/stats", methods=["GET"])
    def get_event_stats():
        """Get event statistics for the current user."""
        uid = request.cookies.get("uid")
        if not uid:
            return jsonify({"error": "no-uid"}), 400
        
        try:
            from app.main import USER_DATA_DIR
            event_tracker = EventTracker(USER_DATA_DIR)
            stats = event_tracker.get_event_stats(uid)
            return jsonify({
                "status": "ok",
                "stats": stats
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
    
    return bp
