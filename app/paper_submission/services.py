import json
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .models import PaperSubmissionResult
from .utils import get_client_ip, check_daily_limit, increment_daily_limit
from .ai_cache import AICacheManager
from .user_data import UserDataManager
from .ai_checker import AIContentChecker


class PaperSubmissionService:
    """Main service for handling paper submissions."""
    
    def __init__(self, 
                 user_data_manager: UserDataManager,
                 ai_cache_manager: AICacheManager,
                 ai_checker: AIContentChecker,
                 limit_file: Path,
                 daily_limit: int,
                 summary_dir: Path,
                 llm_config,
                 paper_config,
                 save_summary_func=None,
                 max_pdf_size_mb: int = 20,
                 index_page_module=None):
        self.user_data_manager = user_data_manager
        self.ai_cache_manager = ai_cache_manager
        self.ai_checker = ai_checker
        self.limit_file = limit_file
        self.daily_limit = daily_limit
        self.summary_dir = summary_dir
        self.llm_config = llm_config
        self.paper_config = paper_config
        self.save_summary_func = save_summary_func
        self.max_pdf_size_mb = max_pdf_size_mb
        self.index_page_module = index_page_module
        self.progress_cache = {}  # Store progress for each task
        self.progress_cache_file = Path("data/progress_cache.json")
        self.progress_cache_file.parent.mkdir(exist_ok=True)
        self._load_progress_cache()
    
    def _load_progress_cache(self):
        """Load progress cache from file."""
        try:
            if self.progress_cache_file.exists():
                with open(self.progress_cache_file, 'r') as f:
                    self.progress_cache = json.load(f)
        except Exception as e:
            print(f"Failed to load progress cache: {e}")
            self.progress_cache = {}
    
    def _save_progress_cache(self):
        """Save progress cache to file."""
        try:
            with open(self.progress_cache_file, 'w') as f:
                json.dump(self.progress_cache, f, indent=2)
        except Exception as e:
            print(f"Failed to save progress cache: {e}")
    
    def _update_progress(self, task_id: str, step: str, progress: int, details: str = ""):
        """Update progress for a specific task."""
        self.progress_cache[task_id] = {
            "step": step,
            "progress": progress,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self._save_progress_cache()
    
    def get_progress(self, task_id: str) -> Dict[str, Any]:
        """Get progress for a specific task."""
        return self.progress_cache.get(task_id, {
            "step": "unknown",
            "progress": 0,
            "details": "任务未找到",
            "timestamp": datetime.now().isoformat()
        })
    
    def submit_paper(self, paper_url: str, uid: str) -> PaperSubmissionResult:
        """Submit a paper URL for processing."""
        task_id = str(uuid.uuid4())
        self._update_progress(task_id, "starting", 0, "正在初始化...")
        
        try:
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
            
            # Check daily limit
            client_ip = get_client_ip()
            if not check_daily_limit(client_ip, self.limit_file, self.daily_limit):
                self._update_progress(task_id, "error", 0, "每日限额已用完")
                return PaperSubmissionResult(
                    success=False,
                    message="您今天已经提交了3篇论文，请明天再试。",
                    error="Daily limit exceeded",
                    task_id=task_id
                )
            
            # Import paper_summarizer module
            import paper_summarizer as ps
            
            # Step 1: Resolve PDF URL
            self._update_progress(task_id, "resolving", 10, "正在解析PDF链接...")
            try:
                pdf_url = ps.resolve_pdf_url(paper_url)
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                    "success": False,
                    "error": f"PDF resolution failed: {str(e)}"
                })
                
                self._update_progress(task_id, "error", 0, f"PDF解析失败: {str(e)}")
                return PaperSubmissionResult(
                    success=False,
                    message=f"无法解析PDF链接: {str(e)}",
                    error=f"PDF resolution failed: {str(e)}",
                    task_id=task_id
                )
            
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
                pdf_path = ps.download_pdf(pdf_url, max_size_mb=self.max_pdf_size_mb, progress_callback=download_progress_callback)
                self._update_progress(task_id, "downloading", 40, "PDF下载完成")
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                    "success": False,
                    "error": f"PDF download failed: {str(e)}"
                })
                
                self._update_progress(task_id, "error", 0, f"PDF下载失败: {str(e)}")
                return PaperSubmissionResult(
                    success=False,
                    message=f"PDF下载失败: {str(e)}",
                    error=f"PDF download failed: {str(e)}",
                    task_id=task_id
                )
            
            # Step 3: Extract text
            self._update_progress(task_id, "extracting", 50, "正在提取文本...")
            try:
                md_path = ps.extract_markdown(pdf_path)
                text_content = md_path.read_text(encoding="utf-8")
                self._update_progress(task_id, "extracting", 60, "文本提取完成")
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                    "success": False,
                    "error": f"Text extraction failed: {str(e)}"
                })
                
                self._update_progress(task_id, "error", 0, f"文本提取失败: {str(e)}")
                return PaperSubmissionResult(
                    success=False,
                    message=f"文本提取失败: {str(e)}",
                    error=f"Text extraction failed: {str(e)}",
                    task_id=task_id
                )
            
            # Step 4: Check if paper is AI-related (with caching)
            self._update_progress(task_id, "checking", 70, "正在检查AI相关性...")
            is_ai, confidence, tags = self.ai_checker.check_paper_ai_relevance(text_content, paper_url)
            self._update_progress(task_id, "checking", 80, f"AI检查完成 (置信度: {confidence:.2f})")
            
            # Check if paper has already been processed successfully
            already_processed = self.user_data_manager.has_processed_paper(uid, paper_url)
            
            # Only increment daily limit if paper hasn't been processed before
            if not already_processed:
                increment_daily_limit(client_ip, self.limit_file)
            
            if not is_ai:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                    "success": False,
                    "error": "Not AI paper"
                })

                print(f"Not AI paper: {paper_url}, confidence: {confidence}, tags: {tags}")
                
                self._update_progress(task_id, "error", 0, "论文不是AI相关")
                return PaperSubmissionResult(
                    success=False,
                    message="抱歉，我们只接受AI相关的论文。根据分析，这篇论文不属于AI领域。",
                    error="Not AI paper",
                    confidence=confidence,
                    task_id=task_id
                )
            
            # Step 5: Process the paper using existing pipeline
            self._update_progress(task_id, "summarizing", 85, "正在生成摘要...")
            try:
                # Use the same summarization logic as in feed_paper_summarizer_service
                import feed_paper_summarizer_service as fps
                
                # Extract arXiv ID from the paper URL first
                arxiv_id = None
                try:
                    # Try to extract arXiv ID from URL
                    if "arxiv.org" in paper_url:
                        import re
                        match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', paper_url)
                        if match:
                            arxiv_id = match.group(1)
                    elif "huggingface.co" in paper_url:
                        # For HuggingFace papers, use a different extraction method
                        import re
                        match = re.search(r'papers/(\d+\.\d+)', paper_url)
                        if match:
                            arxiv_id = match.group(1)
                except Exception:
                    pass
                
                # If we couldn't extract arXiv ID, we'll use a fallback
                if not arxiv_id:
                    # Use a hash of the URL as fallback ID
                    import hashlib
                    arxiv_id = hashlib.md5(paper_url.encode()).hexdigest()[:8]
                
                # Check if this paper already exists to preserve first creation time
                existing_summary_path = self.summary_dir / f"{arxiv_id}.json"
                first_created_at = None
                if existing_summary_path.exists():
                    try:
                        existing_data = json.loads(existing_summary_path.read_text(encoding="utf-8"))
                        existing_service_data = existing_data.get("service_data", {})
                        first_created_at = existing_service_data.get("first_created_at") or existing_service_data.get("created_at")
                    except Exception:
                        pass
                
                # Process the paper
                summary_path, _, paper_subject = fps._summarize_url(
                    paper_url,
                    api_key=self.llm_config.api_key,
                    base_url=self.llm_config.base_url,
                    provider=self.llm_config.provider,
                    model=self.llm_config.model,
                    max_input_char=self.llm_config.max_input_char,
                    extract_only=False,
                    local=False,
                    max_workers=self.paper_config.max_workers
                )
                
                self._update_progress(task_id, "summarizing", 95, "摘要生成完成")
                
                if summary_path:
                    # Read the generated summary content
                    summary_content = summary_path.read_text(encoding="utf-8")
                    
                    # Read the generated tags
                    tags_path = self.summary_dir / f"{arxiv_id}.tags.json"
                    tags = {"top": [], "tags": []}
                    if tags_path.exists():
                        try:
                            tags = json.loads(tags_path.read_text(encoding="utf-8"))
                        except Exception:
                            pass
                    
                    # Create AI judgment data
                    ai_judgment = {
                        "is_ai": is_ai,
                        "confidence": confidence,
                        "tags": tags
                    }
                    
                    # Save with service record
                    if self.save_summary_func:
                        self.save_summary_func(
                            arxiv_id=arxiv_id,
                            summary_content=summary_content,
                            tags=tags,
                            source_type="user",
                            user_id=uid,
                            original_url=paper_url,
                            ai_judgment=ai_judgment,
                            first_created_at=first_created_at
                        )
                    else:
                        # Fallback: save directly
                        summary_path.write_text(summary_content, encoding="utf-8")
                    
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
                    
                    self._update_progress(task_id, "completed", 100, "论文处理完成")
                    return PaperSubmissionResult(
                        success=True,
                        message="论文提交成功！",
                        summary_path=str(summary_path),
                        paper_subject=paper_subject,
                        task_id=task_id
                    )
                else:
                    # Save failed upload attempt
                    self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                        "success": False,
                        "error": "Summary generation failed"
                    })
                    
                    self._update_progress(task_id, "error", 0, "摘要生成失败")
                    return PaperSubmissionResult(
                        success=False,
                        message="论文处理失败，请稍后重试。",
                        error="Summary generation failed",
                        task_id=task_id
                    )
                    
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                    "success": False,
                    "error": f"Processing failed: {str(e)}"
                })
                
                self._update_progress(task_id, "error", 0, f"Processing failed: {str(e)}")
                return PaperSubmissionResult(
                    success=False,
                    message=f"论文处理失败: {str(e)}",
                    error=f"Processing failed: {str(e)}",
                    task_id=task_id
                )
                
        except Exception as e:
            self._update_progress(task_id, "error", 0, f"Server error: {str(e)}")
            return PaperSubmissionResult(
                success=False,
                message=f"服务器错误: {str(e)}",
                error=f"Server error: {str(e)}",
                task_id=task_id
            )
    
    def get_uploaded_urls(self, uid: str) -> list:
        """Get uploaded URLs for a user."""
        return self.user_data_manager.get_uploaded_urls(uid)
    
    def get_user_quota(self, uid: str) -> Dict[str, Any]:
        """Get user's current quota information."""
        from datetime import date, datetime, timedelta
        
        client_ip = get_client_ip()
        today = date.today().isoformat()
        
        try:
            if self.limit_file.exists():
                with open(self.limit_file, 'r', encoding='utf-8') as f:
                    limits = json.load(f)
            else:
                limits = {}
            
            # Clean up old entries
            limits = {k: v for k, v in limits.items() if v['date'] == today}
            
            current_count = limits.get(client_ip, {}).get('count', 0)
            remaining = max(0, self.daily_limit - current_count)
            
            # Calculate next reset time (tomorrow at midnight)
            tomorrow = date.today() + timedelta(days=1)
            next_reset = datetime.combine(tomorrow, datetime.min.time())
            
            return {
                "daily_limit": self.daily_limit,
                "used": current_count,
                "remaining": remaining,
                "next_reset": next_reset.isoformat(),
                "next_reset_formatted": next_reset.strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            # Return default values on error
            return {
                "daily_limit": self.daily_limit,
                "used": 0,
                "remaining": self.daily_limit,
                "next_reset": (datetime.now() + timedelta(days=1)).isoformat(),
                "next_reset_formatted": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            }
    
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
