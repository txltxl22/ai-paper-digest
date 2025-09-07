"""
Factory for creating visitor stats module.
"""
from pathlib import Path
from typing import List
from .services import VisitorStatsService
from .routes import create_visitor_stats_blueprint


def get_admin_required_template() -> str:
    """Load admin required template HTML from the UI directory (no inline fallback)."""
    template_path = Path(__file__).parent.parent.parent / "ui" / "admin-required.html"
    return template_path.read_text(encoding='utf-8')


def create_visitor_stats_module(
    user_data_dir: Path,
    user_service
) -> dict:
    """Create visitor stats module with service and routes.
    
    Args:
        user_data_dir: Directory to store visitor stats data files
        user_service: User service for authentication
    
    Returns:
        Dictionary containing the service and blueprint
    """
    # Create visitor stats service
    visitor_stats_service = VisitorStatsService(user_data_dir)
    
    # Get admin required template
    admin_required_template = get_admin_required_template()
    
    # Create routes
    blueprint = create_visitor_stats_blueprint(
        visitor_stats_service=visitor_stats_service,
        user_service=user_service,
        admin_required_template=admin_required_template
    )
    
    return {
        "service": visitor_stats_service,
        "blueprint": blueprint
    }
