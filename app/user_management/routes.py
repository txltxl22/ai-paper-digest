"""
User management routes for authentication and read status.
"""
from flask import Blueprint, request, jsonify
from .services import UserService


def create_user_routes(user_service: UserService) -> Blueprint:
    """Create user management routes."""
    bp = Blueprint('user_management', __name__)
    
    @bp.route("/set_user", methods=["POST"])
    def set_user():
        """Set user ID and create session."""
        uid = request.form.get("uid", "").strip()
        return user_service.create_user_session(uid)
    
    @bp.route("/mark_read/<arxiv_id>", methods=["POST"])
    def mark_read(arxiv_id):
        """Mark a paper as read."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        user_data = user_service.get_user_data(uid)
        user_data.mark_as_read(arxiv_id)
        return jsonify({"status": "ok"})
    
    @bp.route("/unmark_read/<arxiv_id>", methods=["POST"])
    def unmark_read(arxiv_id):
        """Mark a paper as unread."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        user_data = user_service.get_user_data(uid)
        user_data.mark_as_unread(arxiv_id)
        return jsonify({"status": "ok"})
    
    @bp.route("/reset", methods=["POST"])
    def reset_read():
        """Reset all read status for the user."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        user_data = user_service.get_user_data(uid)
        user_data.save_read_map({})
        return jsonify({"status": "ok"})
    
    return bp
