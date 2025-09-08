"""
Search routes for paper search functionality.
"""
from flask import Blueprint, request, jsonify, render_template_string
from typing import List, Dict, Any
from .services import SearchService


def create_search_routes(search_service: SearchService) -> Blueprint:
    """Create search routes."""
    bp = Blueprint('search', __name__, url_prefix='/search')
    
    @bp.route("/", methods=["GET"])
    def search_papers():
        """Search papers by query."""
        query = request.args.get("q", "").strip()
        search_type = request.args.get("search_type", "all").strip()
        search_fields = request.args.getlist("fields")
        
        # Determine search fields based on search type
        if not search_fields:
            if search_type == "all":
                search_fields = ['title', 'content', 'tags']
            elif search_type == "content":
                search_fields = ['title', 'content']
            elif search_type == "tags":
                search_fields = ['tags']
            else:
                search_fields = ['title', 'content', 'tags']
        
        if not query:
            return jsonify({
                "results": [],
                "query": query,
                "total": 0,
                "message": "Please provide a search query"
            })
        
        try:
            results = search_service.search(query, search_fields)
            return jsonify({
                "results": results,
                "query": query,
                "total": len(results),
                "fields": search_fields,
                "search_type": search_type
            })
        except Exception as e:
            return jsonify({
                "error": "Search failed",
                "message": str(e),
                "results": [],
                "total": 0
            }), 500
    
    @bp.route("/suggest", methods=["GET"])
    def search_suggestions():
        """Get search suggestions based on partial query."""
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 2:
            return jsonify({"suggestions": []})
        
        try:
            # Get suggestions from tags and titles
            content_index = search_service._build_content_index()
            suggestions = set()
            
            for paper in content_index:
                # Add tag suggestions
                for tag_list_name in ['tags', 'top_tags', 'detail_tags']:
                    tags = paper.get(tag_list_name, [])
                    for tag in tags:
                        if query.lower() in tag.lower():
                            suggestions.add(tag)
                
                # Add title suggestions (first few words)
                title = paper.get('title', '')
                if title and query.lower() in title.lower():
                    words = title.split()[:3]  # First 3 words
                    suggestions.add(' '.join(words))
            
            # Convert to list and sort
            suggestions = sorted(list(suggestions))[:10]  # Limit to 10 suggestions
            
            return jsonify({"suggestions": suggestions})
        except Exception as e:
            return jsonify({"suggestions": []}), 500
    
    return bp
