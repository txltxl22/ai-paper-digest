"""
Summary detail routes for individual paper viewing.
"""
from flask import Blueprint, request, render_template_string, abort, url_for, jsonify
from .services import SummaryLoader, SummaryRenderer
from .processing_tracker import ProcessingTracker
from summary_service.paper_info_extractor import PaperInfoExtractor
from summary_service.record_manager import save_summary_with_service_record, get_structured_summary
from config_manager import get_llm_config, get_paper_processing_config
from pathlib import Path
import logging
import threading

logger = logging.getLogger(__name__)


def create_summary_detail_routes(
    summary_loader: SummaryLoader,
    summary_renderer: SummaryRenderer,
    detail_template: str,
    summary_dir: Path,
    processing_tracker: ProcessingTracker,
    user_service=None
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
        
        # Get current logged-in user ID from cookies (for deep read feature)
        current_user_id = request.cookies.get("uid")
        
        # Check user favorite/read status if user is logged in
        is_favorited = False
        is_read = False
        uid = None
        if current_user_id and user_service:
            uid = current_user_id
            user_data = user_service.get_user_data(uid)
            favorites_map = user_data.load_favorites_map()
            read_map = user_data.load_read_map()
            is_favorited = arxiv_id in favorites_map
            is_read = arxiv_id in read_map
        
        return render_template_string(
            detail_template,
            content=rendered["html_content"],
            arxiv_id=arxiv_id,
            top_tags=rendered["top_tags"],
            detail_tags=rendered["detail_tags"],
            source_type=rendered["source_type"],
            user_id=rendered["user_id"],
            current_user_id=current_user_id,
            uid=uid,
            is_favorited=is_favorited,
            is_read=is_read,
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
            mark_favorite_url=url_for("user_management.mark_favorite", arxiv_id="__ID__").replace("__ID__", ""),
            unmark_favorite_url=url_for("user_management.unmark_favorite", arxiv_id="__ID__").replace("__ID__", ""),
            mark_todo_url=url_for("user_management.mark_todo", arxiv_id="__ID__").replace("__ID__", ""),
            unmark_todo_url=url_for("user_management.unmark_todo", arxiv_id="__ID__").replace("__ID__", ""),
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
        
        # Record deep read action as user interest signal
        # This is a strong interest indicator - user explicitly requested full analysis
        if user_service:
            try:
                user_data = user_service.get_user_data(uid)
                user_data.mark_as_deep_read(arxiv_id)
                logger.info(f"Recorded deep read action for paper {arxiv_id} by user {uid}")
            except Exception as e:
                # Don't fail the deep read request if recording fails
                logger.warning(f"Failed to record deep read action for {arxiv_id} by {uid}: {e}")
            
        try:
            # Check if already processing
            if processing_tracker.is_processing(arxiv_id, uid):
                return jsonify({
                    "success": True,
                    "message": "深度阅读正在生成中，请稍候",
                    "already_processing": True
                })
            
            # Load existing summary record
            record = summary_loader.load_summary(arxiv_id)
            if not record:
                return jsonify({"error": "Paper not found"}), 404
            
            original_url = record.service_data.original_url
            if not original_url:
                # Try to construct arXiv URL
                original_url = f"https://arxiv.org/abs/{arxiv_id}"
            
            # Start tracking
            logger.info(f"Attempting to start processing for {arxiv_id} by user {uid}")
            tracking_started = processing_tracker.start_processing(arxiv_id, uid)
            logger.info(f"Tracking start result for {arxiv_id} by user {uid}: {tracking_started}")
            
            if not tracking_started:
                # Another request started processing just now
                logger.info(f"Processing already started for {arxiv_id} by user {uid}")
                return jsonify({
                    "success": True,
                    "message": "深度阅读正在生成中，请稍候",
                    "already_processing": True
                })
            
            # Verify the job was created
            is_now_processing = processing_tracker.is_processing(arxiv_id, uid)
            logger.info(f"Verification: is_processing({arxiv_id}, {uid}) = {is_now_processing}")
            
            # Run summarization in background thread
            def process_in_background():
                try:
                    logger.info(f"[THREAD] Starting background deep read processing for {arxiv_id} by user {uid}")
                    # We import inside the function to avoid circular imports
                    import paper_summarizer as ps
                    
                    # Get config values
                    llm_config = get_llm_config()
                    paper_config = get_paper_processing_config()
                    
                    # Ensure session exists
                    if not hasattr(ps, "SESSION") or ps.SESSION is None:
                        from summary_service.pdf_processor import build_session
                        ps.SESSION = build_session()
                    
                    logger.info(f"[THREAD] Calling summarize_paper_url for {arxiv_id}")
                    result = ps.summarize_paper_url(
                        url=original_url,
                        abstract_only=False, # Force full deep read
                        extract_only=False,
                        local=False, # Force re-process to get full content
                        max_input_char=llm_config.max_input_char,
                        max_workers=paper_config.max_workers
                    )
                    
                    logger.info(f"[THREAD] Summarization result for {arxiv_id}: success={result.is_success}")
                    if result.is_success:
                        processing_tracker.mark_completed(arxiv_id, uid)
                        logger.info(f"[THREAD] Deep read completed for {arxiv_id} by user {uid}")
                    else:
                        error_msg = getattr(result, 'error', 'Summarization failed')
                        processing_tracker.mark_failed(arxiv_id, uid, error_msg)
                        logger.error(f"[THREAD] Deep read failed for {arxiv_id} by user {uid}: {error_msg}")
                except Exception as e:
                    error_msg = str(e)
                    processing_tracker.mark_failed(arxiv_id, uid, error_msg)
                    logger.exception(f"[THREAD] Error generating deep read for {arxiv_id} by user {uid}: {e}")
            
            # Start background thread (non-daemon so it completes)
            thread = threading.Thread(target=process_in_background, daemon=False, name=f"DeepRead-{arxiv_id}-{uid}")
            thread.start()
            logger.info(f"Started background thread for deep read: {arxiv_id} by user {uid}, thread_id={thread.ident}")
            
            # Double-check the job is in the tracker
            final_check = processing_tracker.is_processing(arxiv_id, uid)
            logger.info(f"Final check: is_processing({arxiv_id}, {uid}) = {final_check}")
            
            return jsonify({
                "success": True,
                "message": "深度阅读生成已开始，请稍候",
                "processing": True
            })
                
        except Exception as e:
            logger.error(f"Error starting deep read for {arxiv_id}: {e}")
            # Try to mark as failed if we started tracking
            try:
                processing_tracker.mark_failed(arxiv_id, uid, str(e))
            except:
                pass
            return jsonify({
                "error": "Internal server error",
                "message": f"深度阅读生成出错: {str(e)}"
            }), 500
    
    def _extract_paper_title(arxiv_id: str) -> str:
        """Extract paper title from summary record, fallback to arxiv_id."""
        try:
            record = summary_loader.load_summary(arxiv_id)
            if record and record.summary_data and record.summary_data.structured_content:
                paper_info = record.summary_data.structured_content.paper_info
                # Prefer Chinese title, fallback to English title
                if paper_info.title_zh and paper_info.title_zh.strip():
                    return paper_info.title_zh.strip()
                elif paper_info.title_en and paper_info.title_en.strip():
                    return paper_info.title_en.strip()
        except Exception as e:
            logger.debug(f"Could not extract title for {arxiv_id}: {e}")
        # Fallback to arxiv_id if title not available
        return arxiv_id

    @bp.route("/api/deep_read/status", methods=["GET"])
    def deep_read_status():
        """Get processing status for current user's deep read jobs."""
        uid = request.cookies.get("uid")
        if not uid:
            return jsonify({"error": "Login required"}), 401
        
        try:
            processing_jobs = processing_tracker.get_processing_jobs(uid)
            
            # Verify processing jobs - check if summary is actually complete
            verified_processing = []
            for job in processing_jobs:
                # Check if summary file exists and is not abstract-only
                record = summary_loader.load_summary(job.arxiv_id)
                if record:
                    # If summary exists and is not abstract-only, it's actually complete
                    if not record.service_data.is_abstract_only:
                        # Summary is complete, mark it as completed
                        processing_tracker.mark_completed(job.arxiv_id, uid)
                        logger.info(f"Auto-marked {job.arxiv_id} as completed (summary file verified)")
                    else:
                        # Still abstract-only, keep as processing
                        verified_processing.append(job)
                else:
                    # Summary doesn't exist yet, keep as processing
                    verified_processing.append(job)
            
            completed_jobs = processing_tracker.get_completed_jobs(uid, limit=10)
            logger.info(f"Completed jobs for user {uid}: {completed_jobs}")
            return jsonify({
                "processing": [
                    {
                        "arxiv_id": job.arxiv_id,
                        "title": _extract_paper_title(job.arxiv_id),
                        "started_at": job.started_at.isoformat()
                    }
                    for job in verified_processing
                ],
                "completed": [
                    {
                        "arxiv_id": job.arxiv_id,
                        "title": _extract_paper_title(job.arxiv_id),
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None
                    }
                    for job in completed_jobs
                ]
            })
        except Exception as e:
            logger.exception(f"Error getting deep read status for user {uid}: {e}")
            return jsonify({
                "error": "Internal server error",
                "message": "Failed to get processing status"
            }), 500
    
    @bp.route("/api/deep_read/<arxiv_id>/dismiss", methods=["POST"])
    def dismiss_deep_read(arxiv_id):
        """Dismiss a completed deep read job from status bar."""
        uid = request.cookies.get("uid")
        if not uid:
            return jsonify({"error": "Login required"}), 401
        
        try:
            processing_tracker.dismiss_job(arxiv_id, uid)
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"Error dismissing job: {e}")
            return jsonify({
                "error": "Internal server error",
                "message": "Failed to dismiss job"
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
