#!/usr/bin/env python3
"""
Simple runner script for the Flask application.
This script ensures the correct Python path is set and runs the app.
"""

import sys
import os
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import and run the Flask app
from app.main import app

if __name__ == "__main__":
    print("🚀 Starting Flask application...")
    print(f"📁 Working directory: {current_dir}")
    print(f"🐍 Python path includes: {current_dir}")
    
    # Import configuration
    from config_manager import get_app_config
    app_config = get_app_config()
    
    # Run the Flask app
    app.run(
        host=app_config.host,
        port=app_config.port,
        debug=app_config.debug
    )
