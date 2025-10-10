"""
User management routes for authentication and read status.
"""
from flask import Blueprint, request, jsonify, render_template_string
from .services import UserService


def create_user_routes(user_service: UserService) -> Blueprint:
    """Create user management routes."""
    bp = Blueprint('user_management', __name__)
    
    @bp.route("/set_user", methods=["POST"])
    def set_user():
        """Set user ID and create session."""
        uid = request.form.get("uid", "").strip()
        password = request.form.get("password", "").strip()
        return user_service.create_user_session(uid, password)
    
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
    
    @bp.route("/mark_favorite/<arxiv_id>", methods=["POST"])
    def mark_favorite(arxiv_id):
        """Mark a paper as favorite."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        user_data = user_service.get_user_data(uid)
        user_data.mark_as_favorite(arxiv_id)
        user_data.mark_as_read(arxiv_id)
        # Remove from todo list since favorite marks as read
        user_data.unmark_as_todo(arxiv_id)
        return jsonify({"status": "ok"})
    
    @bp.route("/unmark_favorite/<arxiv_id>", methods=["POST"])
    def unmark_favorite(arxiv_id):
        """Remove a paper from favorites."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        user_data = user_service.get_user_data(uid)
        user_data.unmark_as_favorite(arxiv_id)
        user_data.unmark_as_read(arxiv_id)  # Allow paper to return to index page
        return jsonify({"status": "ok"})
    
    @bp.route("/mark_todo/<arxiv_id>", methods=["POST"])
    def mark_todo(arxiv_id):
        """Mark a paper as todo."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        user_data = user_service.get_user_data(uid)
        user_data.mark_as_todo(arxiv_id)
        return jsonify({"status": "ok"})
    
    @bp.route("/unmark_todo/<arxiv_id>", methods=["POST"])
    def unmark_todo(arxiv_id):
        """Remove a paper from todo list."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        user_data = user_service.get_user_data(uid)
        user_data.unmark_as_todo(arxiv_id)
        return jsonify({"status": "ok"})
    
    @bp.route("/set_password", methods=["POST"])
    def set_password():
        """Set password for the current user."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        data = request.get_json()
        password = data.get("password", "").strip()
        
        if not password:
            return jsonify({"error": "Password cannot be empty"}), 400
        
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters long"}), 400
        
        success = user_service.set_user_password(uid, password)
        if success:
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Failed to set password"}), 500
    
    @bp.route("/change_password", methods=["POST"])
    def change_password():
        """Change password for the current user."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        data = request.get_json()
        old_password = data.get("old_password", "").strip()
        new_password = data.get("new_password", "").strip()
        
        if not new_password:
            return jsonify({"error": "New password cannot be empty"}), 400
        
        if len(new_password) < 6:
            return jsonify({"error": "New password must be at least 6 characters long"}), 400
        
        success = user_service.change_user_password(uid, old_password, new_password)
        if success:
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Invalid old password or failed to change password"}), 400
    
    @bp.route("/remove_password", methods=["POST"])
    def remove_password():
        """Remove password for the current user."""
        uid, error = user_service.require_auth_json()
        if error:
            return jsonify(error), 400
        
        data = request.get_json()
        password = data.get("password", "").strip()
        
        success = user_service.remove_user_password(uid, password)
        if success:
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Invalid password or failed to remove password"}), 400
    
    @bp.route("/password_status", methods=["GET"])
    def password_status():
        """Get password status for a user."""
        # Check if uid parameter is provided (for checking other users)
        uid_param = request.args.get("uid")
        if uid_param:
            uid = uid_param.strip()
            if not uid:
                return jsonify({"error": "Invalid uid parameter"}), 400
        else:
            # Use current authenticated user
            uid, error = user_service.require_auth_json()
            if error:
                return jsonify(error), 400
        
        user_data = user_service.get_user_data(uid)
        has_password = user_data.has_password()
        is_admin = user_service.is_admin_user(uid)
        requires_password = is_admin or has_password
        
        return jsonify({
            "has_password": has_password,
            "is_admin": is_admin,
            "requires_password": requires_password
        })
    
    return bp
