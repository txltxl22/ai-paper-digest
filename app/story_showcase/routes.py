"""
Story showcase routes for serving the development story page.

Design Note:
- Static files (HTML, CSS, JS) are in /story_showcase/ at project root
- Flask routes are in /app/story_showcase/ following the app's module pattern
- This keeps the story showcase self-contained and separate from /ui/
"""
from pathlib import Path
from flask import Blueprint, send_from_directory, abort


def create_story_showcase_routes() -> Blueprint:
    """
    Create story showcase routes blueprint.
    
    Serves static files from the /story_showcase/ directory at the /story/ URL prefix.
    This design keeps the story showcase self-contained and separate from the main /ui/.
    """
    # Get the story_showcase directory path (relative to project root)
    story_dir = Path(__file__).parent.parent.parent / "story_showcase"
    
    bp = Blueprint('story_showcase', __name__, url_prefix='/story')
    
    @bp.route('/')
    def story_index():
        """Serve the story showcase index page."""
        index_path = story_dir / "index.html"
        if index_path.exists():
            return send_from_directory(str(story_dir), 'index.html', mimetype="text/html")
        else:
            abort(404)
    
    @bp.route('/css/<path:filename>')
    def story_css(filename):
        """Serve CSS files from the story_showcase/css directory."""
        css_dir = story_dir / "css"
        return send_from_directory(str(css_dir), filename, mimetype="text/css")
    
    @bp.route('/js/<path:filename>')
    def story_js(filename):
        """Serve JavaScript files from the story_showcase/js directory."""
        js_dir = story_dir / "js"
        return send_from_directory(str(js_dir), filename, mimetype="application/javascript")
    
    return bp

