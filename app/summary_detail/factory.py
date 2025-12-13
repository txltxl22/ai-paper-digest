"""
Factory for creating summary detail module.
"""
from pathlib import Path
from .services import SummaryLoader, SummaryRenderer
from .routes import create_summary_detail_routes
from .processing_tracker import ProcessingTracker


def create_summary_detail_module(summary_dir, detail_template: str, data_dir: Path = None, user_service=None) -> dict:
    """Create summary detail module with services and routes.
    
    Args:
        summary_dir: Directory containing summary files
        detail_template: Template string for detail view
        data_dir: Optional directory for persistence files
        user_service: Optional user service for authentication and user data
        
    Returns:
        Dictionary containing the services and blueprint
    """
    # Create services
    summary_loader = SummaryLoader(summary_dir)
    summary_renderer = SummaryRenderer()
    summary_renderer.loader = summary_loader  # Pass loader reference to renderer
    
    # Create processing tracker with persistence
    persistence_file = None
    if data_dir:
        persistence_file = data_dir / "deep_read_processing.json"
    processing_tracker = ProcessingTracker(persistence_file=persistence_file)
    
    # Create routes
    blueprint = create_summary_detail_routes(
        summary_loader, 
        summary_renderer, 
        detail_template, 
        summary_dir,
        processing_tracker,
        user_service=user_service
    )
    
    return {
        "loader": summary_loader,
        "renderer": summary_renderer,
        "blueprint": blueprint,
        "processing_tracker": processing_tracker
    }
