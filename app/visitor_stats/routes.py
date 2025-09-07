"""
Visitor Stats Routes

Flask routes for the visitor stats subsystem.
"""

from flask import Blueprint, request, jsonify, render_template_string, render_template
from functools import wraps
from typing import Callable

from .services import VisitorStatsService


def create_visitor_stats_blueprint(
    visitor_stats_service: VisitorStatsService,
    user_service,
    admin_required_template: str
) -> Blueprint:
    """Create visitor stats blueprint with routes.
    
    Args:
        visitor_stats_service: The visitor stats service instance
        user_service: The user service for authentication
        admin_required_template: Template to show when admin access is required
        
    Returns:
        Flask blueprint with visitor stats routes
    """
    blueprint = Blueprint('visitor_stats', __name__, url_prefix='/stats')
    
    def admin_required(f: Callable) -> Callable:
        """Decorator to require admin access."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user from session
            user_id = request.cookies.get('uid')
            if not user_id:
                return render_template_string(admin_required_template, 
                                           message="Please log in to access visitor stats.")
            
            # Check if user is admin
            if not user_service.is_admin_user(user_id):
                return render_template_string(admin_required_template, 
                                           message="Admin access required to view visitor stats.")
            
            return f(*args, **kwargs)
        return decorated_function
    
    @blueprint.route('/', methods=['GET'])
    @admin_required
    def stats_dashboard():
        """Main stats dashboard page."""
        days = request.args.get('days', 30, type=int)
        stats = visitor_stats_service.get_visitor_stats(days)
        device_stats = visitor_stats_service.get_device_stats(days)
        anonymous_visitors = visitor_stats_service.get_anonymous_visitor_details(days)
        logged_users = visitor_stats_service.get_logged_user_details(days)
        
        # Calculate max page views for chart scaling
        max_pv = max([data['pv'] for data in stats.daily_stats.values()] + [1])
        
        return render_template('stats-dashboard.html', 
                             stats=stats, 
                             days=days, 
                             max=max, 
                             max_pv=max_pv,
                             device_stats=device_stats, 
                             anonymous_visitors=anonymous_visitors, 
                             logged_users=logged_users)
    
    @blueprint.route('/api/stats', methods=['GET'])
    @admin_required
    def api_stats():
        """API endpoint for visitor statistics."""
        days = request.args.get('days', 30, type=int)
        stats = visitor_stats_service.get_visitor_stats(days)
        return jsonify(stats.to_dict())
    
    @blueprint.route('/api/daily', methods=['GET'])
    @admin_required
    def api_daily_stats():
        """API endpoint for daily statistics."""
        days = request.args.get('days', 7, type=int)
        daily_stats = visitor_stats_service.get_daily_stats(days)
        return jsonify(daily_stats)
    
    @blueprint.route('/api/actions', methods=['GET'])
    @admin_required
    def api_action_distribution():
        """API endpoint for action distribution."""
        days = request.args.get('days', 30, type=int)
        action_dist = visitor_stats_service.get_action_distribution(days)
        return jsonify(action_dist)
    
    @blueprint.route('/api/pages', methods=['GET'])
    @admin_required
    def api_top_pages():
        """API endpoint for top pages."""
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 10, type=int)
        top_pages = visitor_stats_service.get_top_pages(days, limit)
        return jsonify(top_pages)
    
    @blueprint.route('/api/devices', methods=['GET'])
    @admin_required
    def api_device_stats():
        """API endpoint for device and browser statistics."""
        days = request.args.get('days', 30, type=int)
        device_stats = visitor_stats_service.get_device_stats(days)
        return jsonify(device_stats)
    
    @blueprint.route('/api/anonymous', methods=['GET'])
    @admin_required
    def api_anonymous_visitors():
        """API endpoint for anonymous visitor details."""
        days = request.args.get('days', 30, type=int)
        anonymous_visitors = visitor_stats_service.get_anonymous_visitor_details(days)
        return jsonify(anonymous_visitors)
    
    @blueprint.route('/api/logged-users', methods=['GET'])
    @admin_required
    def api_logged_users():
        """API endpoint for logged-in user details."""
        days = request.args.get('days', 30, type=int)
        logged_users = visitor_stats_service.get_logged_user_details(days)
        return jsonify(logged_users)
    
    @blueprint.route('/track', methods=['POST'])
    def track_page_view():
        """Track a page view (no admin required)."""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        user_id = data.get('user_id', 'anonymous')
        page = data.get('page', '')
        referrer = data.get('referrer')
        user_agent = data.get('user_agent') or request.headers.get('User-Agent')
        ip_address = request.remote_addr
        session_id = request.cookies.get('session_id') or data.get('session_id')
        
        visitor_stats_service.track_page_view(
            user_id=user_id,
            page=page,
            referrer=referrer,
            user_agent=user_agent,
            ip_address=ip_address,
            session_id=session_id
        )
        
        return jsonify({'status': 'success'})
    
    @blueprint.route('/track/action', methods=['POST'])
    def track_action():
        """Track an action (no admin required)."""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        user_id = data.get('user_id', 'anonymous')
        action_type = data.get('action_type', '')
        page = data.get('page')
        arxiv_id = data.get('arxiv_id')
        metadata = data.get('metadata', {})
        user_agent = data.get('user_agent') or request.headers.get('User-Agent')
        ip_address = request.remote_addr
        session_id = request.cookies.get('session_id') or data.get('session_id')
        
        visitor_stats_service.track_action(
            user_id=user_id,
            action_type=action_type,
            page=page,
            arxiv_id=arxiv_id,
            metadata=metadata,
            user_agent=user_agent,
            ip_address=ip_address,
            session_id=session_id
        )
        
        return jsonify({'status': 'success'})
    
    return blueprint
