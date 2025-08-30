"""
Factory for creating fetch module.
"""
from pathlib import Path
from .services import FetchService
from .routes import create_fetch_routes


def create_fetch_module(working_directory: Path, user_service, index_page_module) -> dict:
    """Create fetch module with services and routes.
    
    Args:
        working_directory: Directory where fetch commands will be executed
        user_service: User management service for authentication
        index_page_module: Index page module for cache clearing
        
    Returns:
        Dictionary containing the service and blueprint
    """
    # Create fetch service
    fetch_service = FetchService(working_directory)
    
    # Create routes
    blueprint = create_fetch_routes(fetch_service, user_service, index_page_module)
    
    return {
        "service": fetch_service,
        "blueprint": blueprint
    }
