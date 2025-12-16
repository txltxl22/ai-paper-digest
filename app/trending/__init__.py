"""
Trending module for tag trend analysis and display.
"""

from .services import TrendingService
from .routes import create_trending_routes
from .factory import create_trending_module

__all__ = ['TrendingService', 'create_trending_routes', 'create_trending_module']

