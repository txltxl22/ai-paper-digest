import os
import json
import re
import argparse
from pathlib import Path
from datetime import datetime, date, timezone, timedelta

# Import configuration management
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config_manager import ConfigManager



from flask import (
    Flask,
    render_template_string,
    abort,
    send_from_directory,
    request,
    make_response,
    jsonify,
    redirect,
    url_for,
    Response,
)
from werkzeug.middleware.proxy_fix import ProxyFix
import markdown
import math

app = Flask(__name__, template_folder='../ui', static_folder='../ui')
app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_proto = 1,     # trust 1 hop for X-Forwarded-Proto
        x_host  = 1,     # trust 1 hop for X-Forwarded-Host
        x_prefix= 1)     # <-- pay attention to X-Forwarded-Prefix

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Load configuration
config_manager = ConfigManager()
paths_config = config_manager.get_paths_config()
app_config = config_manager.get_app_config()
llm_config = config_manager.get_llm_config()
paper_config = config_manager.get_paper_processing_config()

# Set up directories
SUMMARY_DIR = Path(__file__).parent.parent / paths_config.summary_dir
USER_DATA_DIR = Path(__file__).parent.parent / paths_config.user_data_dir
PDF_DIR = Path(__file__).parent.parent / paths_config.papers_dir
MD_DIR = Path(__file__).parent.parent / paths_config.markdown_dir
DATA_DIR = Path(__file__).parent.parent / "data"

# Create directories
SUMMARY_DIR.mkdir(exist_ok=True)
USER_DATA_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
MD_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# Service Record Management
# -----------------------------------------------------------------------------

# Import service record functions from the decoupled module
from summary_service.record_manager import (
    create_service_record,
    save_summary_with_service_record as save_summary_with_service_record_base,
    load_summary_with_service_record as load_summary_with_service_record_base,
    migrate_legacy_summaries_to_service_record
)

def save_summary_with_service_record(arxiv_id: str, summary_content: str, tags: dict, 
                                   source_type: str = "system", user_id: str = None,
                                   original_url: str = None, ai_judgment: dict = None,
                                   first_created_at: str = None):
    """Save a summary with its service record in JSON format.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_content: The markdown summary content
        tags: Tags dictionary with top and detail tags
        source_type: Either "system" or "user"
        user_id: The user ID who uploaded the paper (if source_type is "user")
        original_url: The original URL of the paper
        ai_judgment: AI judgment data if available
        first_created_at: The original creation time (for resubmissions)
    """
    save_summary_with_service_record_base(
        arxiv_id=arxiv_id,
        summary_content=summary_content,
        tags=tags,
        summary_dir=SUMMARY_DIR,
        source_type=source_type,
        user_id=user_id,
        original_url=original_url,
        ai_judgment=ai_judgment,
        first_created_at=first_created_at
    )

def load_summary_with_service_record(arxiv_id: str) -> dict:
    """Load a summary with its service record.
    
    Args:
        arxiv_id: The arXiv ID of the paper
    
    Returns:
        Dictionary containing service_data and summary_data, or None if not found
    """
    return load_summary_with_service_record_base(arxiv_id, SUMMARY_DIR)


# Initialize user management module
from app.user_management.factory import create_user_management_module

user_management_module = create_user_management_module(
    user_data_dir=USER_DATA_DIR,
    admin_user_ids=app_config.admin_user_ids
)

# Initialize index page module
from app.index_page.factory import create_index_page_module

# Initialize summary detail module
from app.summary_detail.factory import create_summary_detail_module

# Initialize fetch module
from app.fetch.factory import create_fetch_module

# Load templates
with open(Path(__file__).parent.parent / "ui" / "index.html", "r", encoding="utf-8") as f:
    INDEX_TEMPLATE = f.read()

with open(Path(__file__).parent.parent / "ui" / "detail.html", "r", encoding="utf-8") as f:
    DETAIL_TEMPLATE = f.read()

# Initialize search module first
from app.search.factory import create_search_module

search_module = create_search_module(summary_dir=SUMMARY_DIR)

index_page_module = create_index_page_module(
    summary_dir=SUMMARY_DIR,
    user_service=user_management_module["service"],
    index_template=INDEX_TEMPLATE,
    detail_template=DETAIL_TEMPLATE,
    paper_config=paper_config,
    search_service=search_module["service"]
)

summary_detail_module = create_summary_detail_module(
    summary_dir=SUMMARY_DIR,
    detail_template=DETAIL_TEMPLATE,
    data_dir=DATA_DIR
)

fetch_module = create_fetch_module(
    working_directory=Path(__file__).parent.parent,
    user_service=user_management_module["service"],
    index_page_module=index_page_module
)

# Initialize paper submission module
from app.paper_submission.factory import create_paper_submission_module

paper_submission_module = create_paper_submission_module(
    user_data_dir=USER_DATA_DIR,
    data_dir=DATA_DIR,
    summary_dir=SUMMARY_DIR,
    prompts_dir=Path(__file__).parent.parent / "summary_service" / "prompts",
    llm_config=llm_config,
    paper_config=paper_config,
    daily_limit=paper_config.daily_submission_limit,
    save_summary_func=save_summary_with_service_record,
    index_page_module=index_page_module
)

# Register blueprints
app.register_blueprint(user_management_module["blueprint"])
app.register_blueprint(index_page_module["blueprint"])
app.register_blueprint(summary_detail_module["blueprint"])
app.register_blueprint(fetch_module["blueprint"])
app.register_blueprint(paper_submission_module["blueprint"])


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

# Event tracking functions are now handled by the decoupled EventTracker class
# This function is kept for backward compatibility but delegates to the tracker
def append_event(uid: str, event_type: str, arxiv_id: str | None = None, meta: dict | None = None, ts: str | None = None):
    """Append a single analytics event for the user (backward compatibility).

    This function is now a wrapper around the decoupled EventTracker.
    """
    from app.event_tracking.event_tracker import EventTracker
    tracker = EventTracker(USER_DATA_DIR)
    tracker.track_event(uid, event_type, arxiv_id, meta, ts)

# -----------------------------------------------------------------------------
# Event Tracking System
# -----------------------------------------------------------------------------

# Initialize event tracking module
from app.event_tracking.factory import create_event_tracking_module

event_tracking_module = create_event_tracking_module(USER_DATA_DIR)

# Register event tracking blueprint
app.register_blueprint(event_tracking_module["blueprint"])

# Initialize visitor stats module
from app.visitor_stats.factory import create_visitor_stats_module

visitor_stats_module = create_visitor_stats_module(
    user_data_dir=USER_DATA_DIR,
    user_service=user_management_module["service"]
)

# Register visitor stats blueprint
app.register_blueprint(visitor_stats_module["blueprint"])

# Register search blueprint
app.register_blueprint(search_module["blueprint"])

# -----------------------------------------------------------------------------
# Templates (plain strings — no Python f-strings)                               
# -----------------------------------------------------------------------------

BASE_CSS = open(os.path.join('ui', 'base.css'), 'r', encoding='utf-8').read()

# -----------------------------------------------------------------------------
# Template Context Processors (for cache busting)
# -----------------------------------------------------------------------------

def get_file_version(filepath: str) -> str:
    """Get version string based on file modification time for cache busting."""
    try:
        full_path = Path(__file__).parent.parent / filepath
        if full_path.exists():
            mtime = full_path.stat().st_mtime
            # Use modification time as version (hex format for shorter URLs)
            return hex(int(mtime))[2:]
    except Exception:
        pass
    # Fallback to timestamp if file doesn't exist
    return hex(int(datetime.now().timestamp()))[2:]

@app.context_processor
def inject_versioned_urls():
    """Inject versioned URL helpers into template context."""
    def static_css_versioned(filename: str) -> str:
        """Generate versioned URL for CSS files."""
        base_url = url_for('static_css', filename=filename)
        version = get_file_version(f'ui/css/{filename}')
        return f"{base_url}?v={version}"
    
    def base_css_versioned() -> str:
        """Generate versioned URL for base.css."""
        base_url = url_for('base_css')
        version = get_file_version('ui/base.css')
        return f"{base_url}?v={version}"
    
    return {
        'static_css_versioned': static_css_versioned,
        'base_css_versioned': base_css_versioned,
    }

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@app.route("/test", methods=["GET"])
def test_endpoint():
    """Test endpoint to verify routing is working."""
    return jsonify({
        "status": "ok",
        "message": "Test endpoint working",
        "path": request.path,
        "url": request.url,
        "headers": dict(request.headers),
        "remote_addr": request.remote_addr
    })


@app.get("/assets/base.css")
def base_css():
    """Serve base.css with cache control headers."""
    response = Response(BASE_CSS, mimetype="text/css")
    # Set cache headers - allow caching but with validation
    response.headers['Cache-Control'] = 'public, max-age=31536000, must-revalidate'
    return response

# Unified static file routes for consistent url_for usage
@app.get("/static/css/<path:filename>")
def static_css(filename):
    """Serve CSS files from the ui/css directory with cache control headers."""
    response = send_from_directory('../ui/css', filename, mimetype="text/css")
    # Set cache headers - allow caching but with validation
    response.headers['Cache-Control'] = 'public, max-age=31536000, must-revalidate'
    return response


@app.get("/static/js/<path:filename>")
def static_js(filename):
    """Serve JavaScript files from the ui/js directory."""
    return send_from_directory('../ui/js', filename, mimetype="application/javascript")


@app.get("/static/favicon.svg")
def static_favicon_svg():
    """Serve the static SVG favicon file."""
    return send_from_directory('../ui', 'favicon.svg', mimetype="image/svg+xml")


@app.get("/favicon.ico")
def root_favicon_ico():
    """Serve the root favicon.ico file."""
    # Serve SVG favicon for ICO requests
    return send_from_directory('../ui', 'favicon.svg', mimetype="image/svg+xml")


@app.get("/robots.txt")
def robots_txt():
    """Serve robots.txt file."""
    return send_from_directory('../ui', 'robots.txt', mimetype="text/plain")


@app.get("/manifest.json")
def manifest_json():
    """Serve PWA manifest.json file."""
    return send_from_directory('../ui', 'manifest.json', mimetype="application/manifest+json")


@app.get("/service-worker.js")
def service_worker():
    """Serve service worker for PWA functionality."""
    return send_from_directory('../ui/js', 'service-worker.js', mimetype="application/javascript")


@app.get("/sitemap.xml")
def sitemap_xml():
    """Generate and serve XML sitemap for all paper summaries."""
    from xml.etree.ElementTree import Element, SubElement, tostring
    from datetime import datetime
    
    # Create root element
    urlset = Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    urlset.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    urlset.set('xsi:schemaLocation', 'http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd')
    
    # Add homepage
    url = SubElement(urlset, 'url')
    SubElement(url, 'loc').text = request.url_root.rstrip('/')
    SubElement(url, 'lastmod').text = datetime.now().strftime('%Y-%m-%d')
    SubElement(url, 'changefreq').text = 'daily'
    SubElement(url, 'priority').text = '1.0'
    
    # Get all entries from the index page module
    entry_scanner = index_page_module["scanner"]
    entries_meta = entry_scanner.scan_entries_meta()
    
    # Add each paper summary page
    for entry in entries_meta:
        arxiv_id = entry.get("id")
        if arxiv_id:
            url = SubElement(urlset, 'url')
            summary_url = f"{request.url_root.rstrip('/')}/summary/{arxiv_id}"
            SubElement(url, 'loc').text = summary_url
            
            # Use updated time if available
            updated = entry.get("updated")
            if updated:
                if isinstance(updated, datetime):
                    SubElement(url, 'lastmod').text = updated.strftime('%Y-%m-%d')
                elif isinstance(updated, str):
                    try:
                        dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                        SubElement(url, 'lastmod').text = dt.strftime('%Y-%m-%d')
                    except:
                        SubElement(url, 'lastmod').text = datetime.now().strftime('%Y-%m-%d')
            else:
                SubElement(url, 'lastmod').text = datetime.now().strftime('%Y-%m-%d')
            
            SubElement(url, 'changefreq').text = 'weekly'
            SubElement(url, 'priority').text = '0.8'
    
    # Convert to string
    xml_string = tostring(urlset, encoding='utf-8', xml_declaration=True)
    response = make_response(xml_string)
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return response


@app.get("/sitemap-index.xml")
def sitemap_index_xml():
    """Generate and serve sitemap index XML."""
    from xml.etree.ElementTree import Element, SubElement, tostring
    from datetime import datetime
    
    # Create root element
    sitemapindex = Element('sitemapindex')
    sitemapindex.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    
    # Add main sitemap
    sitemap = SubElement(sitemapindex, 'sitemap')
    SubElement(sitemap, 'loc').text = f"{request.url_root.rstrip('/')}/sitemap.xml"
    SubElement(sitemap, 'lastmod').text = datetime.now().strftime('%Y-%m-%d')
    
    # Convert to string
    xml_string = tostring(sitemapindex, encoding='utf-8', xml_declaration=True)
    response = make_response(xml_string)
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return response


# Event tracking routes are now handled by the decoupled event tracking system
# The /event endpoint is registered via the event tracking blueprint


# -----------------------------------------------------------------------------
# Common Bot/Scanner Endpoints
# -----------------------------------------------------------------------------

@app.get("/actuator/health")
def actuator_health():
    """Health check endpoint for monitoring tools and cloud platforms."""
    return jsonify({
        "status": "UP",
        "service": "ai-paper-digest"
    }), 200


@app.get("/.well-known/security.txt")
def security_txt():
    """Security policy file as per RFC 9116."""
    security_content = """Contact: mailto:security@example.com
Expires: 2026-12-31T23:59:59.000Z
Preferred-Languages: en
"""
    response = make_response(security_content)
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return response

# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Flask application for paper summaries")
    parser.add_argument("--port", type=int, help="Port to run the server on")
    parser.add_argument("--host", type=str, help="Host to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Override configuration with command line arguments
    if args.port:
        app_config.port = args.port
    if args.host:
        app_config.host = args.host
    if args.debug:
        app_config.debug = args.debug
    
    print(f"✅ Serving summaries from {SUMMARY_DIR.resolve()}")
    print(f"📋 Configuration loaded:")
    print(f"   - LLM Provider: {llm_config.provider}")
    print(f"   - Base URL: {llm_config.base_url}")
    print(f"   - Model: {llm_config.model}")
    print(f"   - Daily Limit: {paper_config.daily_submission_limit}")
    print(f"   - Max Workers: {paper_config.max_workers}")
    print(f"   - Server: {app_config.host}:{app_config.port}")
    app.run(
        host=app_config.host, 
        port=app_config.port, 
        debug=app_config.debug
    )