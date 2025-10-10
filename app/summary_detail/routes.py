"""
Summary detail routes for individual paper viewing.
"""
from flask import Blueprint, request, render_template_string, abort, url_for, jsonify
from .services import SummaryLoader, SummaryRenderer
from summary_service.paper_info_extractor import PaperInfoExtractor
from summary_service.record_manager import save_summary_with_service_record
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def create_summary_detail_routes(
    summary_loader: SummaryLoader,
    summary_renderer: SummaryRenderer,
    detail_template: str,
    summary_dir: Path
) -> Blueprint:
    """Create summary detail routes."""
    bp = Blueprint('summary_detail', __name__)
    
    @bp.route("/summary/<arxiv_id>")
    def view_summary(arxiv_id):
        """View individual paper summary."""
        # Load summary data
        record = summary_loader.load_summary(arxiv_id)
        if not record:
            abort(404)
        
        summary_data = record["summary_data"]
        service_data = record["service_data"]
        
        # Render summary
        rendered = summary_renderer.render_summary(summary_data, service_data)
        
        return render_template_string(
            detail_template,
            content=rendered["html_content"],
            arxiv_id=arxiv_id,
            top_tags=rendered["top_tags"],
            detail_tags=rendered["detail_tags"],
            source_type=rendered["source_type"],
            user_id=rendered["user_id"],
            original_url=rendered["original_url"],
            abstract=rendered["abstract"],
            # Add URL variables for JavaScript
            mark_read_url=url_for("user_management.mark_read", arxiv_id="__ID__").replace("__ID__", ""),
            unmark_read_url=url_for("user_management.unmark_read", arxiv_id="__ID__").replace("__ID__", ""),
            reset_url=url_for("user_management.reset_read"),
            admin_fetch_url=url_for("fetch.admin_fetch_latest"),
            admin_stream_url=url_for("fetch.admin_fetch_latest_stream")
        )
    
    @bp.route("/api/abstract/<arxiv_id>")
    def get_abstract(arxiv_id):
        """Get abstract for a paper, fetching on-demand if not cached."""
        try:
            # Load existing summary record
            record = summary_loader.load_summary(arxiv_id)
            if not record:
                return jsonify({"error": "Paper not found"}), 404
            
            service_data = record["service_data"]
            summary_data = record["summary_data"]
            
            # Check if abstract is already cached
            cached_abstract = service_data.get("abstract")
            if cached_abstract:
                return jsonify({
                    "abstract": cached_abstract,
                    "cached": True
                })
            
            # Fetch abstract on-demand
            original_url = service_data.get("original_url")
            if not original_url:
                # Try to construct arXiv URL
                original_url = f"https://arxiv.org/abs/{arxiv_id}"
            
            extractor = PaperInfoExtractor()
            try:
                paper_info = extractor.get_paper_info(original_url)
                if paper_info.get("success") and paper_info.get("abstract"):
                    abstract = paper_info["abstract"]
                    
                    # Save the abstract to the service record
                    save_summary_with_service_record(
                        arxiv_id=arxiv_id,
                        summary_content=summary_data.get("markdown_content", ""),
                        tags=summary_data.get("tags", {}),
                        summary_dir=summary_dir,
                        source_type=service_data.get("source_type", "system"),
                        user_id=service_data.get("user_id"),
                        original_url=original_url,
                        ai_judgment=service_data.get("ai_judgment", {}),
                        first_created_at=service_data.get("first_created_at"),
                        abstract=abstract
                    )
                    
                    logger.info(f"📄 Fetched and cached abstract for {arxiv_id}")
                    return jsonify({
                        "abstract": abstract,
                        "cached": False
                    })
                else:
                    return jsonify({
                        "error": "Failed to extract abstract",
                        "message": "Abstract not available for this paper"
                    }), 404
            finally:
                extractor.close()
                
        except Exception as e:
            logger.error(f"Error fetching abstract for {arxiv_id}: {e}")
            return jsonify({
                "error": "Internal server error",
                "message": "Failed to fetch abstract"
            }), 500
    
    return bp
