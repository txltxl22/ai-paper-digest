"""
Factory for creating user management module.
"""
from pathlib import Path
from typing import List
from .services import UserService
from .routes import create_user_routes


def create_user_management_module(
    user_data_dir: Path,
    admin_user_ids: List[str]
) -> dict:
    """Create user management module with service and routes.
    
    Args:
        user_data_dir: Directory to store user data files
        admin_user_ids: List of admin user IDs
    
    Returns:
        Dictionary containing the service and blueprint
    """
    # Create user data directory
    user_data_dir.mkdir(exist_ok=True)
    
    # Create user service
    user_service = UserService(user_data_dir, admin_user_ids)
    
    # Create routes
    blueprint = create_user_routes(user_service)
    
    return {
        "service": user_service,
        "blueprint": blueprint
    }
