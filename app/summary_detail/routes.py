"""
Summary detail routes for individual paper viewing.
"""
from flask import Blueprint, request, render_template_string, abort, url_for
from .services import SummaryLoader, SummaryRenderer


def create_summary_detail_routes(
    summary_loader: SummaryLoader,
    summary_renderer: SummaryRenderer,
    detail_template: str
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
            tags=rendered["tags"],
            source_type=rendered["source_type"],
            user_id=rendered["user_id"],
            original_url=rendered["original_url"],
            # Add URL variables for JavaScript
            mark_read_url=url_for("user_management.mark_read", arxiv_id="__ID__").replace("__ID__", ""),
            unmark_read_url=url_for("user_management.unmark_read", arxiv_id="__ID__").replace("__ID__", ""),
            reset_url=url_for("user_management.reset_read"),
                    admin_fetch_url=url_for("fetch.admin_fetch_latest"),
        admin_stream_url=url_for("fetch.admin_fetch_latest_stream")
        )
    
    return bp
