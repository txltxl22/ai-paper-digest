"""
Summary detail routes for individual paper viewing.
"""
from flask import Blueprint, request, render_template_string, abort, url_for, jsonify
from .services import SummaryLoader, SummaryRenderer
from summary_service.paper_info_extractor import PaperInfoExtractor
from summary_service.record_manager import save_summary_with_service_record, get_structured_summary
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
        
        # Render summary using SummaryRecord model
        rendered = summary_renderer.render_summary(record)
        
        # Extract English title from PaperInfo
        structured_summary = record.summary_data.structured_content
        english_title = structured_summary.paper_info.title_en if structured_summary else None
        
        is_abstract_only = record.service_data.is_abstract_only
        
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
            english_title=english_title,
            one_sentence_summary=rendered.get("one_sentence_summary", ""),
            is_abstract_only=is_abstract_only,
            created_at=record.service_data.created_at,
            updated_at=record.summary_data.updated_at,
            # Add URL variables for JavaScript
            mark_read_url=url_for("user_management.mark_read", arxiv_id="__ID__").replace("__ID__", ""),
            unmark_read_url=url_for("user_management.unmark_read", arxiv_id="__ID__").replace("__ID__", ""),
            reset_url=url_for("user_management.reset_read"),
            admin_fetch_url=url_for("fetch.admin_fetch_latest"),
            admin_stream_url=url_for("fetch.admin_fetch_latest_stream"),
            deep_read_url=url_for("summary_detail.deep_read", arxiv_id=arxiv_id)
        )

    @bp.route("/api/summary/<arxiv_id>/deep_read", methods=["POST"])
    def deep_read(arxiv_id):
        """Trigger deep read (full summarization) for a paper."""
        # Check user login
        uid = request.cookies.get("uid")
        if not uid:
            return jsonify({"error": "Login required", "message": "请先登录以使用深度阅读功能"}), 401
            
        try:
            # Load existing summary record
            record = summary_loader.load_summary(arxiv_id)
            if not record:
                return jsonify({"error": "Paper not found"}), 404
            
            original_url = record.service_data.original_url
            if not original_url:
                # Try to construct arXiv URL
                original_url = f"https://arxiv.org/abs/{arxiv_id}"
                
            # Trigger full summarization
            # We import inside the function to avoid circular imports
            import paper_summarizer as ps
            
            # Ensure session exists
            if not hasattr(ps, "SESSION") or ps.SESSION is None:
                from summary_service.pdf_processor import build_session
                ps.SESSION = build_session()
                
            result = ps.summarize_paper_url(
                url=original_url,
                abstract_only=False, # Force full deep read
                extract_only=False,
                local=False # Force re-process to get full content
            )
            
            if result.is_success:
                return jsonify({
                    "success": True,
                    "message": "深度阅读生成成功",
                    "reload": True
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "深度阅读生成失败"
                }), 500
                
        except Exception as e:
            logger.error(f"Error generating deep read for {arxiv_id}: {e}")
            return jsonify({
                "error": "Internal server error",
                "message": f"深度阅读生成出错: {str(e)}"
            }), 500
    
    @bp.route("/api/abstract/<arxiv_id>")
    def get_abstract(arxiv_id):
        """Get abstract for a paper, fetching on-demand if not cached."""
        try:
            # Load existing summary record
            record = summary_loader.load_summary(arxiv_id)
            if not record:
                return jsonify({"error": "Paper not found"}), 404
            
            # Get abstract from PaperInfo using helper function
            from summary_service.record_manager import get_structured_summary
            structured_summary = get_structured_summary(arxiv_id, summary_dir)
            if structured_summary and structured_summary.paper_info.abstract:
                return jsonify({
                    "abstract": structured_summary.paper_info.abstract,
                    "cached": True
                })
            
            # Fetch abstract on-demand
            original_url = record.service_data.original_url
            if not original_url:
                original_url = f"https://arxiv.org/abs/{arxiv_id}"
            
            extractor = PaperInfoExtractor()
            try:
                paper_info = extractor.get_paper_info(original_url)
                if paper_info and paper_info.abstract:
                    abstract = paper_info.abstract
                    english_title = paper_info.title_en
                    
                    # Update abstract and English title in the existing record without overwriting summary content
                    from summary_service.record_manager import update_service_record_abstract
                    update_service_record_abstract(arxiv_id, abstract, summary_dir, english_title)
                    
                    logger.info(f"📄 Fetched and cached abstract for {arxiv_id}")
                    return jsonify({
                        "abstract": abstract,
                        "english_title": english_title,
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
