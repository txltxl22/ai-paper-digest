"""
Fetch subsystem routes for admin fetch operations.
"""
import logging
from flask import Blueprint, request, jsonify, Response
from .services import FetchService


def create_fetch_routes(fetch_service: FetchService, user_service, index_page_module) -> Blueprint:
    """Create fetch routes."""
    bp = Blueprint('fetch', __name__)
    
    @bp.route("/admin/fetch_latest", methods=["POST"])
    def admin_fetch_latest():
        """Admin route to fetch latest summaries from RSS feed."""
        # Debug logging
        logging.debug(f"DEBUG: Admin fetch_latest called from {request.remote_addr}")
        logging.debug(f"DEBUG: Request headers: {dict(request.headers)}")
        logging.debug(f"DEBUG: Request path: {request.path}")
        logging.debug(f"DEBUG: Request url: {request.url}")
        
        uid = user_service.get_current_user_id()
        if not uid:
            return jsonify({"error": "no-uid"}), 400
        
        if not user_service.is_admin_user(uid):
            return jsonify({"error": "unauthorized"}), 403
        
        try:
            result = fetch_service.execute_fetch()
            
            if result.success:
                # Clear the cache to force refresh of entries
                index_page_module["scanner"]._cache["meta"] = None
                index_page_module["scanner"]._cache["count"] = 0
                index_page_module["scanner"]._cache["latest_mtime"] = 0.0
                
                return jsonify({
                    "status": "success",
                    "message": "Latest summaries fetched successfully",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "summary_stats": result.summary_stats,
                    "return_code": result.return_code
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": result.error_message or f"Feed service failed with return code {result.return_code}",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.return_code
                }), 500
                
        except Exception as exc:
            return jsonify({
                "status": "error",
                "message": f"Failed to run feed service: {str(exc)}"
            }), 500
    
    @bp.route("/admin/fetch_latest_stream", methods=["POST"])
    def admin_fetch_latest_stream():
        """Admin route to stream the feed service output in real-time."""
        # Debug logging
        print(f"DEBUG: Admin fetch_latest_stream called from {request.remote_addr}")
        print(f"DEBUG: Request headers: {dict(request.headers)}")
        print(f"DEBUG: Request path: {request.path}")
        print(f"DEBUG: Request url: {request.url}")
        
        uid = user_service.get_current_user_id()
        if not uid:
            return jsonify({"error": "no-uid"}), 400
        
        if not user_service.is_admin_user(uid):
            return jsonify({"error": "unauthorized"}), 403
        
        def generate():
            try:
                for event in fetch_service.execute_fetch_stream():
                    # Convert StreamEvent to JSON
                    event_data = {
                        "type": event.event_type,
                        "message": event.message
                    }
                    
                    if event.icon:
                        event_data["icon"] = event.icon
                    if event.level:
                        event_data["level"] = event.level
                    if event.status:
                        event_data["status"] = event.status
                    
                    # Convert to JSON string and send as SSE
                    import json
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                    
                    # Clear cache on success
                    if event.event_type == "complete" and event.status == "success":
                        index_page_module["scanner"]._cache["meta"] = None
                        index_page_module["scanner"]._cache["count"] = 0
                        index_page_module["scanner"]._cache["latest_mtime"] = 0.0
                        
            except Exception as exc:
                error_data = {
                    "type": "error",
                    "message": f"执行过程中发生错误: {str(exc)}"
                }
                import json
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                
                complete_data = {
                    "type": "complete",
                    "status": "error",
                    "message": "执行失败"
                }
                yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
    
    return bp
