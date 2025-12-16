"""
Trending routes for API endpoints.
"""
from flask import Blueprint, jsonify, request
from .services import TrendingService


def create_trending_routes(trending_service: TrendingService) -> Blueprint:
    """Create trending routes blueprint."""
    bp = Blueprint('trending', __name__, url_prefix='/api/trending')
    
    @bp.route('/', methods=['GET'])
    def get_trending():
        """
        Get trending tags for a specified period.
        
        Query parameters:
            - period: Number of days (default 7, options: 7, 30)
            - limit: Maximum tags to return (default 15, max 50)
        """
        try:
            period = int(request.args.get('period', 7))
            limit = int(request.args.get('limit', 15))
        except ValueError:
            period = 7
            limit = 15
        
        # Validate period
        if period not in [7, 30]:
            period = 7
        
        # Validate limit
        limit = max(1, min(limit, 50))
        
        trending_tags = trending_service.get_trending_tags(
            period_days=period,
            limit=limit,
            include_growth=True
        )
        
        return jsonify({
            "period_days": period,
            "tags": trending_tags,
            "count": len(trending_tags)
        })
    
    @bp.route('/summary', methods=['GET'])
    def get_trending_summary():
        """Get trending summary for all periods."""
        summary = trending_service.get_trending_summary()
        return jsonify(summary)
    
    @bp.route('/clear-cache', methods=['POST'])
    def clear_cache():
        """Clear the trending cache (admin only)."""
        trending_service.clear_cache()
        return jsonify({"status": "ok", "message": "Cache cleared"})
    
    return bp

