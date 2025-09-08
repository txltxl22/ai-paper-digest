"""
Factory for creating index page module.
"""
from pathlib import Path
from .services import EntryScanner, EntryRenderer
from .routes import create_index_routes


def create_index_page_module(
    summary_dir: Path,
    user_service,
    index_template: str,
    detail_template: str = "",
    paper_config=None,
    search_service=None
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
    
    # Create routes
    blueprint = create_index_routes(entry_scanner, entry_renderer, user_service, index_template, detail_template, paper_config, search_service)
    
    return {
        "scanner": entry_scanner,
        "renderer": entry_renderer,
        "blueprint": blueprint
    }
