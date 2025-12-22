"""
Factory for creating the story showcase module.
"""
from flask import Blueprint
from .routes import create_story_showcase_routes


def create_story_showcase_module() -> dict:
    """
    Create the story showcase module with all its components.
    
    Returns:
        Dictionary containing:
            - blueprint: Flask blueprint for routes
    """
    blueprint = create_story_showcase_routes()
    
    return {
        "blueprint": blueprint
    }

