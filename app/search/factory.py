"""
Search subsystem factory for creating search modules.
"""
from pathlib import Path
from .services import SearchService
from .routes import create_search_routes


def create_search_module(summary_dir: Path) -> dict:
    """Create search module with service and routes."""
    search_service = SearchService(summary_dir)
    search_routes = create_search_routes(search_service)
    
    return {
        "service": search_service,
        "blueprint": search_routes
    }
