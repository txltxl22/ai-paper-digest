from flask import Blueprint, request, jsonify
from typing import Dict, Any

from .services import PaperSubmissionService


def create_paper_submission_routes(paper_submission_service: PaperSubmissionService):
    """Create Flask routes for paper submission functionality."""
    
    paper_submission_bp = Blueprint('paper_submission', __name__)
    
    @paper_submission_bp.route("/uploaded_urls", methods=["GET"])
    def get_uploaded_urls_route():
        """Get uploaded URLs for the current user."""
        uid = request.cookies.get("uid")
        if not uid:
            return jsonify({"error": "Login required"}), 401
        
        try:
            uploaded_urls = paper_submission_service.get_uploaded_urls(uid)
            return jsonify({
                "success": True,
                "uploaded_urls": uploaded_urls
            })
        except Exception as e:
            return jsonify({
                "error": "Failed to get uploaded URLs",
                "message": str(e)
            }), 500
    
    @paper_submission_bp.route("/quota", methods=["GET"])
    def get_user_quota():
        """Get user's current quota information."""
        uid = request.cookies.get("uid")
        if not uid:
            return jsonify({"error": "Login required"}), 401
        
        try:
            quota_info = paper_submission_service.get_user_quota(uid)
            return jsonify({
                "success": True,
                "quota": quota_info
            })
        except Exception as e:
            return jsonify({
                "error": "Failed to get quota information",
                "message": str(e)
            }), 500
    
    @paper_submission_bp.route("/download_progress/<task_id>", methods=["GET"])
    def get_download_progress(task_id):
        """Get download progress for a specific task."""
        try:
            progress = paper_submission_service.get_progress(task_id)
            return jsonify({
                "success": True,
                "progress": progress
            })
        except Exception as e:
            return jsonify({
                "error": "Failed to get progress",
                "message": str(e)
            }), 500
    
    @paper_submission_bp.route("/submit_paper", methods=["POST"])
    def submit_paper():
        """Handle paper URL submission from users."""
        try:
            data = request.get_json()
            if not data or 'url' not in data:
                return jsonify({"error": "Missing URL"}), 400
            
            paper_url = data['url'].strip()
            if not paper_url:
                return jsonify({"error": "Empty URL"}), 400
            
            # Check if user is logged in
            uid = request.cookies.get("uid")
            if not uid:
                return jsonify({
                    "error": "Login required",
                    "message": "请先登录后再提交论文。"
                }), 401
            
            # Submit the paper
            result = paper_submission_service.submit_paper(paper_url, uid)
            
            if result.success:
                return jsonify({
                    "success": True,
                    "message": result.message,
                    "summary_path": result.summary_path,
                    "paper_subject": result.paper_subject,
                    "task_id": result.task_id
                })
            else:
                # Determine appropriate HTTP status code
                if result.error == "Daily limit exceeded":
                    status_code = 429
                elif result.error in ["Empty URL", "Login required"]:
                    status_code = 400
                elif result.error == "Not AI paper":
                    status_code = 400
                else:
                    status_code = 500
                
                return jsonify({
                    "error": result.error,
                    "message": result.message,
                    "confidence": result.confidence,
                    "task_id": result.task_id
                }), status_code
                
        except Exception as e:
            return jsonify({
                "error": "Server error",
                "message": f"服务器错误: {str(e)}"
            }), 500
    
    @paper_submission_bp.route("/ai_cache/stats", methods=["GET"])
    def get_ai_cache_stats():
        """Get AI cache statistics for maintenance."""
        try:
            stats = paper_submission_service.get_ai_cache_stats()
            return jsonify(stats)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @paper_submission_bp.route("/ai_cache/clear", methods=["POST"])
    def clear_ai_cache():
        """Clear AI cache for maintenance."""
        try:
            result = paper_submission_service.clear_ai_cache()
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @paper_submission_bp.route("/ai_cache/entry/<path:url_or_hash>", methods=["GET"])
    def get_ai_cache_entry(url_or_hash):
        """Get specific AI cache entry for maintenance."""
        try:
            result = paper_submission_service.get_ai_cache_entry(url_or_hash)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @paper_submission_bp.route("/ai_cache/reload", methods=["POST"])
    def reload_ai_cache():
        """Reload AI cache from file for maintenance."""
        try:
            result = paper_submission_service.reload_ai_cache()
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return paper_submission_bp
