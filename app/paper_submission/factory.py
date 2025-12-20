from pathlib import Path
from typing import Dict, Any

from .ai_cache import AICacheManager
from .user_data import UserDataManager
from .ai_checker import AIContentChecker
from .services import PaperSubmissionService
from .routes import create_paper_submission_routes


def create_paper_submission_module(
    user_data_dir: Path,
    data_dir: Path,
    summary_dir: Path,
    prompts_dir: Path,
    llm_config,
    paper_config,
    daily_limit: int,
    save_summary_func=None,
    index_page_module=None,
    processing_tracker=None,
    user_service=None
) -> Dict[str, Any]:
    """Create and configure all paper submission components."""
    
    # Create managers
    ai_cache_manager = AICacheManager(data_dir / "ai_judgment_cache.json")
    user_data_manager = UserDataManager(user_data_dir)
    ai_checker = AIContentChecker(ai_cache_manager, llm_config, prompts_dir)
    
    # Create service
    paper_submission_service = PaperSubmissionService(
        user_data_manager=user_data_manager,
        ai_cache_manager=ai_cache_manager,
        ai_checker=ai_checker,
        limit_file=data_dir / "daily_limits.json",
        daily_limit=daily_limit,
        summary_dir=summary_dir,
        llm_config=llm_config,
        paper_config=paper_config,
        save_summary_func=save_summary_func,
        max_pdf_size_mb=paper_config.max_pdf_size_mb,
        index_page_module=index_page_module,
        processing_tracker=processing_tracker,
        user_service=user_service
    )
    
    # Create routes
    paper_submission_bp = create_paper_submission_routes(paper_submission_service)
    
    return {
        "blueprint": paper_submission_bp,
        "service": paper_submission_service,
        "ai_cache_manager": ai_cache_manager,
        "user_data_manager": user_data_manager,
        "ai_checker": ai_checker
    }
