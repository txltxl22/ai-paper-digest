"""
Factory for creating summary detail module.
"""
from .services import SummaryLoader, SummaryRenderer
from .routes import create_summary_detail_routes


def create_summary_detail_module(summary_dir, detail_template: str) -> dict:
    """Create summary detail module with services and routes.
    
    Args:
        summary_dir: Directory containing summary files
        detail_template: Template string for detail view
        
    Returns:
        Dictionary containing the services and blueprint
    """
    # Create services
    summary_loader = SummaryLoader(summary_dir)
    summary_renderer = SummaryRenderer()
    summary_renderer.loader = summary_loader  # Pass loader reference to renderer
    
    # Create routes
    blueprint = create_summary_detail_routes(summary_loader, summary_renderer, detail_template)
    
    return {
        "loader": summary_loader,
        "renderer": summary_renderer,
        "blueprint": blueprint
    }
