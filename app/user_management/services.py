"""
User management services for authentication and session management.
"""
from typing import Optional, List
from flask import request, make_response, redirect, url_for
from .models import UserData


class UserService:
    """Service for user authentication and session management."""
    
    def __init__(self, user_data_dir, admin_user_ids: List[str]):
        self.user_data_dir = user_data_dir
        self.admin_user_ids = admin_user_ids
    
    def get_current_user_id(self) -> Optional[str]:
        """Get the current user ID from cookies."""
        return request.cookies.get("uid")
    
    def is_authenticated(self) -> bool:
        """Check if the current user is authenticated."""
        return bool(self.get_current_user_id())
    
    def is_admin_user(self, uid: str) -> bool:
        """Check if the user is an admin based on configuration."""
        return uid.strip() in self.admin_user_ids
    
    def create_user_session(self, uid: str) -> make_response:
        """Create a user session by setting a cookie."""
        if not uid:
            return redirect(url_for("index_page.index"))
        
        resp = make_response(redirect(url_for("index_page.index")))
        resp.set_cookie("uid", uid, max_age=60 * 60 * 24 * 365 * 3)  # 3-year cookie
        return resp
    
    def get_user_data(self, uid: str) -> UserData:
        """Get user data object for the given user ID."""
        return UserData(uid, self.user_data_dir)
    
    def require_auth(self, redirect_url: str = None) -> Optional[str]:
        """Require authentication, redirect if not authenticated."""
        uid = self.get_current_user_id()
        if not uid:
            if redirect_url:
                return redirect(redirect_url)
            else:
                return redirect(url_for("index_page.index"))
        return uid
    
    def require_auth_json(self) -> tuple[Optional[str], Optional[dict]]:
        """Require authentication for JSON endpoints, return error if not authenticated."""
        uid = self.get_current_user_id()
        if not uid:
            return None, {"error": "no-uid"}
        return uid, None
