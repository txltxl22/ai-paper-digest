import json
from pathlib import Path
from typing import Optional, Dict, Any

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
                 save_summary_func=None):
        self.user_data_manager = user_data_manager
        self.ai_cache_manager = ai_cache_manager
        self.ai_checker = ai_checker
        self.limit_file = limit_file
        self.daily_limit = daily_limit
        self.summary_dir = summary_dir
        self.llm_config = llm_config
        self.paper_config = paper_config
        self.save_summary_func = save_summary_func
    
    def submit_paper(self, paper_url: str, uid: str) -> PaperSubmissionResult:
        """Submit a paper URL for processing."""
        try:
            # Validate input
            if not paper_url or not paper_url.strip():
                return PaperSubmissionResult(
                    success=False,
                    message="Empty URL",
                    error="Empty URL"
                )
            
            paper_url = paper_url.strip()
            
            # Check daily limit
            client_ip = get_client_ip()
            if not check_daily_limit(client_ip, self.limit_file, self.daily_limit):
                return PaperSubmissionResult(
                    success=False,
                    message="您今天已经提交了3篇论文，请明天再试。",
                    error="Daily limit exceeded"
                )
            
            # Import paper_summarizer module
            import paper_summarizer as ps
            
            # Step 1: Resolve PDF URL
            try:
                pdf_url = ps.resolve_pdf_url(paper_url)
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                    "success": False,
                    "error": f"PDF resolution failed: {str(e)}"
                })
                
                return PaperSubmissionResult(
                    success=False,
                    message=f"无法解析PDF链接: {str(e)}",
                    error=f"PDF resolution failed: {str(e)}"
                )
            
            # Step 2: Download PDF
            try:
                pdf_path = ps.download_pdf(pdf_url)
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                    "success": False,
                    "error": f"PDF download failed: {str(e)}"
                })
                
                return PaperSubmissionResult(
                    success=False,
                    message=f"PDF下载失败: {str(e)}",
                    error=f"PDF download failed: {str(e)}"
                )
            
            # Step 3: Extract text
            try:
                md_path = ps.extract_markdown(pdf_path)
                text_content = md_path.read_text(encoding="utf-8")
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                    "success": False,
                    "error": f"Text extraction failed: {str(e)}"
                })
                
                return PaperSubmissionResult(
                    success=False,
                    message=f"文本提取失败: {str(e)}",
                    error=f"Text extraction failed: {str(e)}"
                )
            
            # Step 4: Check if paper is AI-related (with caching)
            is_ai, confidence, tags = self.ai_checker.check_paper_ai_relevance(text_content, paper_url)
            
            # Increment daily limit for any valid PDF upload (regardless of AI content)
            increment_daily_limit(client_ip, self.limit_file)
            
            if not is_ai:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                    "success": False,
                    "error": "Not AI paper"
                })

                print(f"Not AI paper: {paper_url}, confidence: {confidence}, tags: {tags}")
                
                return PaperSubmissionResult(
                    success=False,
                    message="抱歉，我们只接受AI相关的论文。根据分析，这篇论文不属于AI领域。",
                    error="Not AI paper",
                    confidence=confidence
                )
            
            # Step 5: Process the paper using existing pipeline
            try:
                # Use the same summarization logic as in feed_paper_summarizer_service
                import feed_paper_summarizer_service as fps
                
                # Process the paper
                summary_path, _, paper_subject = fps._summarize_url(
                    paper_url,
                    api_key=self.llm_config.api_key,
                    base_url=self.llm_config.base_url,
                    provider=self.llm_config.provider,
                    model=self.llm_config.model,
                    max_input_char=100000,
                    extract_only=False,
                    local=False,
                    max_workers=self.paper_config.max_workers
                )
                
                if summary_path:
                    # Extract arXiv ID from the summary path
                    arxiv_id = summary_path.stem
                    
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
                            ai_judgment=ai_judgment
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
                    
                    # Clear cache to force refresh
                    # Note: This would need to be injected from main.py as well
                    # For now, we'll just return success
                    
                    return PaperSubmissionResult(
                        success=True,
                        message="论文提交成功！",
                        summary_path=str(summary_path),
                        paper_subject=paper_subject
                    )
                else:
                    # Save failed upload attempt
                    self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                        "success": False,
                        "error": "Summary generation failed"
                    })
                    
                    return PaperSubmissionResult(
                        success=False,
                        message="论文处理失败，请稍后重试。",
                        error="Summary generation failed"
                    )
                    
            except Exception as e:
                # Save failed upload attempt
                self.user_data_manager.save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                    "success": False,
                    "error": f"Processing failed: {str(e)}"
                })
                
                return PaperSubmissionResult(
                    success=False,
                    message=f"论文处理失败: {str(e)}",
                    error=f"Processing failed: {str(e)}"
                )
                
        except Exception as e:
            return PaperSubmissionResult(
                success=False,
                message=f"服务器错误: {str(e)}",
                error=f"Server error: {str(e)}"
            )
    
    def get_uploaded_urls(self, uid: str) -> list:
        """Get uploaded URLs for a user."""
        return self.user_data_manager.get_uploaded_urls(uid)
    
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
