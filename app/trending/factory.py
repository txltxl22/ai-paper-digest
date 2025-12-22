"""
Factory for creating the trending module.
"""
from flask import Blueprint
from .services import TrendingService
from .routes import create_trending_routes


def create_trending_module(entry_scanner) -> dict:
    """
    Create the trending module with all its components.
    
    Args:
        entry_scanner: EntryScanner instance from index_page module
    
    Returns:
        Dictionary containing:
            - service: TrendingService instance
            - blueprint: Flask blueprint for routes
    """
    service = TrendingService(entry_scanner)
    blueprint = create_trending_routes(service)
    
    return {
        "service": service,
        "blueprint": blueprint
    }

