"""
Factory for creating index page module.
"""
from pathlib import Path
from .services import EntryScanner, EntryRenderer
from .routes import create_index_routes
from summary_service.recommendations import build_default_engine


def create_index_page_module(
    summary_dir: Path,
    user_service,
    index_template: str,
    detail_template: str = "",
    paper_config=None,
    search_service=None,
    recommendation_engine=None
) -> dict:
    """Create index page module with services and routes.
    
    Args:
        summary_dir: Directory containing summary files
        user_service: User management service
        index_template: HTML template for index page
    
    Returns:
        Dictionary containing the services and blueprint
    """
    # Create services
    entry_scanner = EntryScanner(summary_dir)
    entry_renderer = EntryRenderer(summary_dir)
    
    # Initialize recommendation engine
    recommendation_engine = recommendation_engine or build_default_engine()

    # Create routes
    blueprint = create_index_routes(
        entry_scanner,
        entry_renderer,
        user_service,
        index_template,
        detail_template,
        paper_config,
        search_service,
        recommendation_engine,
    )
    
    return {
        "scanner": entry_scanner,
        "renderer": entry_renderer,
        "blueprint": blueprint,
        "recommendation_engine": recommendation_engine,
    }
