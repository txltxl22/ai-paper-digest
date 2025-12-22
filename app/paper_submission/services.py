import json
import uuid
import threading
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

from .models import PaperSubmissionResult
from .ai_cache import AICacheManager
from .user_data import UserDataManager
from .ai_checker import AIContentChecker
from summary_service.record_manager import load_summary_with_service_record, save_summary_with_service_record

if TYPE_CHECKING:
    from app.quota import QuotaManager


class PaperSubmissionService:
    """Main service for handling paper submissions."""
    
    def __init__(self, 
                 user_data_manager: UserDataManager,
                 ai_cache_manager: AICacheManager,
                 ai_checker: AIContentChecker,
                 summary_dir: Path,
                 llm_config,
                 paper_config,
                 save_summary_func=None,
                 max_pdf_size_mb: int = 20,
                 index_page_module=None,
                 processing_tracker=None,
                 user_service=None,
                 quota_manager: "QuotaManager" = None):
        self.user_data_manager = user_data_manager
        self.ai_cache_manager = ai_cache_manager
        self.ai_checker = ai_checker
        self.summary_dir = summary_dir
        self.llm_config = llm_config
        self.paper_config = paper_config
        self.save_summary_func = save_summary_func
        self.max_pdf_size_mb = max_pdf_size_mb
        self.index_page_module = index_page_module
        self.processing_tracker = processing_tracker  # For deep read tracking
        self.user_service = user_service  # For accessing user data
        self.quota_manager = quota_manager  # For tiered quota management
        self.progress_cache = {}  # Store progress for each task
        self.result_cache = {}  # Store final results for completed tasks
    
    def _update_progress(self, task_id: str, step: str, progress: int, details: str = "", result: Dict[str, Any] = None):
        """Update progress for a specific task."""
        progress_data = {
            "step": step,
            "progress": progress,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        if result:
            progress_data["result"] = result
        self.progress_cache[task_id] = progress_data
    
    def get_progress(self, task_id: str) -> Dict[str, Any]:
        """Get progress for a specific task."""
        if task_id in self.progress_cache:
            return self.progress_cache[task_id]
        else:
            return {
                "step": "unknown",
                "progress": 0,
                "details": "任务未找到",
                "timestamp": datetime.now().isoformat()
            }
    
    def submit_paper(self, paper_url: str, uid: str) -> PaperSubmissionResult:
        """Submit a paper URL for processing asynchronously.
        
        Returns immediately with a task_id. Processing happens in background.
        
        Args:
            paper_url: URL of the paper to process
            uid: User ID, or None for guests
        """
        task_id = str(uuid.uuid4())
        self._update_progress(task_id, "starting", 0, "正在初始化...")
        
        # Track the effective uid for processing tracker (may be pseudo-uid for guests)
        effective_uid = uid
        client_ip = None
        
        # Validate input
        if not paper_url or not paper_url.strip():
            self._update_progress(task_id, "error", 0, "URL为空")
            return PaperSubmissionResult(
                success=False,
                message="Empty URL",
                error="Empty URL",
                task_id=task_id
            )
        
        paper_url = paper_url.strip()
        
        # Check quota using the new tiered system
        if self.quota_manager:
            client_ip = self.quota_manager.get_client_ip()
            quota_result = self.quota_manager.check_only(client_ip, uid)
            
            if not quota_result.allowed:
                self._update_progress(task_id, "error", 0, quota_result.message or "配额已用完")
                return PaperSubmissionResult(
                    success=False,
                    message=quota_result.message or "您的配额已用完，请稍后再试。",
                    error=quota_result.reason or "Quota exceeded",
                    task_id=task_id
                )
            
            # Use pseudo_uid for guests (for tracking)
            if quota_result.pseudo_uid:
                effective_uid = quota_result.pseudo_uid
        
        # Start background processing
        self._update_progress(task_id, "starting", 5, "任务已提交，开始处理...")
        thread = threading.Thread(
            target=self._process_paper_async,
            args=(task_id, paper_url, uid, effective_uid, client_ip),
            daemon=True
        )
        thread.start()
        
        # Return immediately - processing continues in background
        return PaperSubmissionResult(
            success=True,
            message="论文提交成功，正在后台处理...",
            task_id=task_id
        )
    
    def _process_paper_async(self, task_id: str, paper_url: str, uid: str, effective_uid: str, client_ip: str):
        """Process paper in background thread."""
        try:
            # Import paper_summarizer module
            import paper_summarizer as ps
            
            # Step 1: Resolve PDF URL
            self._update_progress(task_id, "resolving", 10, "正在解析PDF链接...")
            try:
                pdf_url = ps.resolve_pdf_url(paper_url, ps.SESSION)
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                    "success": False,
                    "error": f"PDF resolution failed: {str(e)}"
                })
                
                self._update_progress(task_id, "error", 0, f"PDF解析失败: {str(e)}")
                return
            
            # Step 2: Download PDF
            self._update_progress(task_id, "downloading", 20, "正在下载PDF...")
            
            def download_progress_callback(percent, downloaded, total):
                """Progress callback for download."""
                # Map download progress from 20% to 40% of overall progress
                overall_progress = 20 + int((percent / 100) * 20)
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024) if total > 0 else 0
                details = f"正在下载PDF... {percent}% ({downloaded_mb:.1f}MB / {total_mb:.1f}MB)"
                self._update_progress(task_id, "downloading", overall_progress, details)
            
            try:
                pdf_path = ps.download_pdf(pdf_url, output_dir=ps.PDF_DIR, session=ps.SESSION, max_size_mb=self.max_pdf_size_mb, progress_callback=download_progress_callback)
                self._update_progress(task_id, "downloading", 40, "PDF下载完成")
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                    "success": False,
                    "error": f"PDF download failed: {str(e)}"
                })
                
                self._update_progress(task_id, "error", 0, f"PDF下载失败: {str(e)}")
                return
            
            # Step 3: Extract text
            self._update_progress(task_id, "extracting", 50, "正在提取文本...")
            try:
                md_path = ps.extract_markdown(pdf_path, md_dir=ps.MD_DIR)
                text_content = md_path.read_text(encoding="utf-8")
                self._update_progress(task_id, "extracting", 60, "文本提取完成")
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                    "success": False,
                    "error": f"Text extraction failed: {str(e)}"
                })
                
                self._update_progress(task_id, "error", 0, f"文本提取失败: {str(e)}")
                return
            
            # Step 4: Check if paper is AI-related (with caching)
            self._update_progress(task_id, "checking", 70, "正在检查AI相关性...")
            is_ai, confidence, tags = self.ai_checker.check_paper_ai_relevance(text_content, paper_url)
            self._update_progress(task_id, "checking", 80, f"AI检查完成 (置信度: {confidence:.2f})")
            
            # Check if paper has already been processed globally (for all users)
            already_processed = self._check_paper_processed_globally(paper_url)
            
            # Only consume quota if paper hasn't been processed before
            if not already_processed and self.quota_manager:
                # Now actually consume the quota
                consume_result = self.quota_manager.check_and_consume(client_ip, uid)
                if not consume_result.allowed:
                    self._update_progress(task_id, "error", 0, consume_result.message or "配额已用完")
                    return
            
            if not is_ai:
                # If paper is not AI-related but has already been processed globally, allow access
                if already_processed:
                    arxiv_id = self._extract_arxiv_id_from_url(paper_url)
                    # Save user's upload attempt as successful (already processed)
                    self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                        "success": True,
                        "message": "Paper already processed globally (non-AI)",
                        "arxiv_id": arxiv_id
                    })
                    
                    self._update_progress(task_id, "completed", 100, "论文已存在，处理完成", result={
                        "success": True,
                        "summary_url": f"/summary/{arxiv_id}",
                        "message": "这篇论文已经被处理过了，您可以在搜索结果中找到它。"
                    })
                    return
                
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                    "success": False,
                    "error": "Not AI paper"
                })

                print(f"Not AI paper: {paper_url}, confidence: {confidence}, tags: {tags}")
                
                self._update_progress(task_id, "error", 0, "论文不是AI相关 - 抱歉，我们只接受AI相关的论文。")
                return
            
            # Step 5: Process the paper using existing pipeline
            self._update_progress(task_id, "summarizing", 85, "正在生成摘要...")
            try:
                # Use the same summarization logic as in feed_paper_summarizer_service
                import feed_paper_summarizer_service as fps
                
                # Extract arXiv ID from the paper URL using centralized method
                arxiv_id = self._extract_arxiv_id_from_url(paper_url)
                
                # Add to deep read tracking list so user can see progress
                # Use effective_uid which may be pseudo-uid for guests
                if self.processing_tracker:
                    self.processing_tracker.start_processing(arxiv_id, effective_uid)
                
                # Also mark as deep_read in user's data for the deep read status display
                # Only for logged-in users (not pseudo-uid guests)
                if self.user_service and uid and not uid.startswith("ip:"):
                    try:
                        user_data = self.user_service.get_user_data(uid)
                        if user_data:
                            user_data.mark_as_deep_read(arxiv_id)
                    except Exception as e:
                        print(f"Failed to mark paper as deep_read for user {uid}: {e}")
                
                # Check if this paper already exists to preserve first creation time
                first_created_at = None
                existing_record = load_summary_with_service_record(arxiv_id, self.summary_dir)
                if existing_record:
                    first_created_at = existing_record.service_data.first_created_at or existing_record.service_data.created_at
                    
                # If paper already exists globally, update timestamp and save user's attempt
                if already_processed:
                    # Update the updated_at timestamp for the existing paper
                    try:
                        existing_record = load_summary_with_service_record(arxiv_id, self.summary_dir)
                        if existing_record:
                            # Update the updated_at timestamp using Pydantic model
                            existing_record.summary_data.updated_at = datetime.now().isoformat()
                            
                            # Save the updated record using save_summary_with_service_record
                            save_summary_with_service_record(
                                arxiv_id=arxiv_id,
                                summary_content=existing_record.summary_data.structured_content,
                                tags=existing_record.summary_data.tags,
                                summary_dir=self.summary_dir,
                                source_type=existing_record.service_data.source_type,
                                user_id=existing_record.service_data.user_id,
                                original_url=existing_record.service_data.original_url,
                                ai_judgment=existing_record.service_data.ai_judgment,
                                first_created_at=existing_record.service_data.first_created_at,
                                is_abstract_only=existing_record.service_data.is_abstract_only
                            )
                            
                            # Clear index page cache to force refresh
                            if self.index_page_module and hasattr(self.index_page_module.get("scanner"), "clear_cache"):
                                try:
                                    self.index_page_module["scanner"].clear_cache()
                                except Exception as e:
                                    print(f"Failed to clear index cache: {e}")
                    except Exception as e:
                        print(f"Failed to update timestamp for existing paper {arxiv_id}: {e}")
                    
                    # Save user's upload attempt as successful (already processed)
                    self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                        "success": True,
                        "message": "Paper already processed globally",
                        "arxiv_id": arxiv_id
                    })
                    
                    self._update_progress(task_id, "completed", 100, "论文已存在，处理完成", result={
                        "success": True,
                        "summary_url": f"/summary/{arxiv_id}",
                        "message": "这篇论文已经被处理过了，您可以在搜索结果中找到它。"
                    })
                    return
                
                # Process the paper
                result = fps._summarize_url(
                    paper_url,
                    api_key=self.llm_config.api_key,
                    base_url=self.llm_config.base_url,
                    provider=self.llm_config.provider,
                    model=self.llm_config.model,
                    max_input_char=self.llm_config.max_input_char,
                    extract_only=False,
                    local=False,
                    max_workers=self.paper_config.max_workers,
                    abstract_only=False  # User submissions get full deep read
                )
                
                self._update_progress(task_id, "summarizing", 95, "摘要生成完成")
                
                if result.is_success:
                    summary_path = result.summary_path
                    paper_subject = result.paper_subject
                    # The paper summarizer should have created structured data
                    # Check if there's a structured summary JSON file
                    summary_json_path = self.summary_dir / f"{arxiv_id}.json"
                    
                    # Create AI judgment data
                    ai_judgment = {
                        "is_ai": is_ai,
                        "confidence": confidence,
                        "tags": {}  # Will be loaded from existing record if available
                    }
                    
                    # Update the existing service record to mark it as user submission
                    if summary_json_path.exists():
                        try:
                            existing_record = load_summary_with_service_record(arxiv_id, self.summary_dir)
                            
                            if existing_record:
                                # Update service_data to mark as user submission using Pydantic model
                                existing_record.service_data.source_type = "user"
                                existing_record.service_data.user_id = uid
                                existing_record.service_data.original_url = paper_url
                                existing_record.service_data.ai_judgment = ai_judgment
                                # Always preserve first_created_at - use existing if available, otherwise use provided
                                if existing_record.service_data.first_created_at:
                                    # Keep existing first_created_at (never overwrite)
                                    pass
                                elif first_created_at:
                                    existing_record.service_data.first_created_at = first_created_at
                                
                                # Update updated_at timestamp
                                existing_record.summary_data.updated_at = datetime.now().isoformat()
                                
                                # Save the updated record using Pydantic
                                save_summary_with_service_record(
                                    arxiv_id=arxiv_id,
                                    summary_content=existing_record.summary_data.structured_content,
                                    tags=existing_record.summary_data.tags,
                                    summary_dir=self.summary_dir,
                                    source_type=existing_record.service_data.source_type,
                                    user_id=existing_record.service_data.user_id,
                                    original_url=existing_record.service_data.original_url,
                                    ai_judgment=existing_record.service_data.ai_judgment,
                                    first_created_at=existing_record.service_data.first_created_at,
                                    is_abstract_only=existing_record.service_data.is_abstract_only
                                )
                                
                                print(f"✅ Updated service record for {arxiv_id} to mark as user submission")
                            else:
                                # Fallback: try to read and re-save
                                raise Exception("Could not load existing record")
                        except Exception as e:
                            print(f"⚠️ Error updating existing record: {e}")
                            # If we have a result with structured summary, use it
                            if result.structured_summary:
                                from summary_service.models import Tags
                                # Try to load tags from existing record or use empty tags
                                tags_obj = Tags(top=[], tags=[])
                                try:
                                    existing_record = load_summary_with_service_record(arxiv_id, self.summary_dir)
                                    if existing_record:
                                        tags_obj = existing_record.summary_data.tags
                                except Exception:
                                    pass

                                save_summary_with_service_record(
                                    arxiv_id=arxiv_id,
                                    summary_content=result.structured_summary,
                                    tags=tags_obj,
                                    summary_dir=self.summary_dir,
                                    source_type="user",
                                    user_id=uid,
                                    original_url=paper_url,
                                    ai_judgment=ai_judgment,
                                    first_created_at=first_created_at
                                )
                            else:
                                raise e
                    else:
                        # No existing record, but we should have one from the summarization
                        # Use the structured summary from the result
                        if result.structured_summary:
                            from summary_service.models import Tags
                            # Try to load tags from the record that should have been created
                            tags_obj = Tags(top=[], tags=[])
                            try:
                                existing_record = load_summary_with_service_record(arxiv_id, self.summary_dir)
                                if existing_record:
                                    tags_obj = existing_record.summary_data.tags
                            except Exception:
                                pass
                            
                            save_summary_with_service_record(
                                arxiv_id=arxiv_id,
                                summary_content=result.structured_summary,
                                tags=tags_obj,
                                summary_dir=self.summary_dir,
                                source_type="user",
                                user_id=uid,
                                original_url=paper_url,
                                ai_judgment=ai_judgment,
                                first_created_at=first_created_at
                            )
                        else:
                            print(f"⚠️ No structured summary available for {arxiv_id}")
                    
                    # Save successful upload record
                    self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                        "success": True,
                        "summary_path": str(summary_path),
                        "paper_subject": paper_subject
                    })
                    
                    # Clear index page cache to force refresh
                    if self.index_page_module and hasattr(self.index_page_module.get("scanner"), "clear_cache"):
                        try:
                            self.index_page_module["scanner"].clear_cache()
                        except Exception as e:
                            print(f"Failed to clear index cache: {e}")
                    
                    # Mark deep read as completed in tracking
                    if self.processing_tracker:
                        self.processing_tracker.mark_completed(arxiv_id, effective_uid)
                    
                    self._update_progress(task_id, "completed", 100, "论文处理完成", result={
                        "success": True,
                        "summary_url": f"/summary/{arxiv_id}",
                        "message": "论文提交成功！",
                        "summary_path": str(summary_path),
                        "paper_subject": paper_subject
                    })
                    return
                else:
                    # Save failed upload attempt
                    self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                        "success": False,
                        "error": "Summary generation failed"
                    })
                    
                    # Mark deep read as failed in tracking
                    if self.processing_tracker:
                        self.processing_tracker.mark_failed(arxiv_id, effective_uid, "Summary generation failed")
                    
                    self._update_progress(task_id, "error", 0, "摘要生成失败 - 论文处理失败，请稍后重试。")
                    return
                    
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                    "success": False,
                    "error": f"Processing failed: {str(e)}"
                })
                
                # Mark deep read as failed in tracking (arxiv_id might not be set if error happened early)
                if self.processing_tracker and 'arxiv_id' in locals():
                    self.processing_tracker.mark_failed(arxiv_id, effective_uid, str(e))
                
                self._update_progress(task_id, "error", 0, f"处理失败: {str(e)}")
                return
                
        except Exception as e:
            self._update_progress(task_id, "error", 0, f"服务器错误: {str(e)}")
    
    def get_uploaded_urls(self, uid: str) -> list:
        """Get uploaded URLs for a user."""
        return self.user_data_manager.get_uploaded_urls(uid)
    
    def get_user_quota(self, uid: str) -> Dict[str, Any]:
        """Get user's current quota information using the tiered quota system."""
        from datetime import date, datetime, timedelta
        
        if self.quota_manager:
            client_ip = self.quota_manager.get_client_ip()
            quota_info = self.quota_manager.get_quota_info(client_ip, uid)
            
            # Calculate next reset time (tomorrow at midnight)
            tomorrow = date.today() + timedelta(days=1)
            next_reset = datetime.combine(tomorrow, datetime.min.time())
            
            return {
                "tier": quota_info.get("tier", "guest"),
                "daily_limit": quota_info.get("daily_limit"),
                "used": quota_info.get("used_today", 0),
                "remaining": quota_info.get("remaining", 0),
                "is_unlimited": quota_info.get("is_unlimited", False),
                "quota_total": quota_info.get("quota_total"),  # For Pro users
                "quota_remaining": quota_info.get("quota_remaining"),  # For Pro users
                "message": quota_info.get("message", ""),
                "next_reset": next_reset.isoformat(),
                "next_reset_formatted": next_reset.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Fallback for when quota_manager is not available
        return {
            "tier": "unknown",
            "daily_limit": 3,
            "used": 0,
            "remaining": 3,
            "is_unlimited": False,
            "message": "配额系统未初始化",
            "next_reset": (datetime.now() + timedelta(days=1)).isoformat(),
            "next_reset_formatted": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def _check_paper_processed_globally(self, paper_url: str) -> bool:
        """Check if a paper has been processed globally by looking in the summary directory."""
        from summary_service.record_manager import check_paper_processed_globally
        return check_paper_processed_globally(paper_url, self.summary_dir)
    
    def _extract_arxiv_id_from_url(self, paper_url: str) -> str:
        """Extract arXiv ID from paper URL using the same logic as the system."""
        from summary_service.paper_info_extractor import extract_arxiv_id
        import hashlib
        
        # Use the centralized arXiv ID extraction from summary_service
        arxiv_id = extract_arxiv_id(paper_url)
        
        # If we couldn't extract arXiv ID, use a hash of the URL as fallback
        if arxiv_id is None:
            return hashlib.md5(paper_url.encode()).hexdigest()[:8]
        
        return arxiv_id
    
    def get_ai_cache_stats(self) -> Dict[str, Any]:
        """Get AI cache statistics for maintenance."""
        return self.ai_cache_manager.get_cache_stats()
    
    def clear_ai_cache(self) -> Dict[str, Any]:
        """Clear AI cache for maintenance."""
        return self.ai_cache_manager.clear_cache()
    
    def get_ai_cache_entry(self, url_or_hash: str) -> Dict[str, Any]:
        """Get specific AI cache entry for maintenance."""
        return self.ai_cache_manager.get_cache_entry(url_or_hash)
    
    def reload_ai_cache(self) -> Dict[str, Any]:
        """Reload AI cache from file for maintenance."""
        return self.ai_cache_manager.reload_cache()
