import os
import json
import subprocess
import re
import string
import argparse
from pathlib import Path
from datetime import datetime, date, timezone, timedelta

# Import configuration management
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config_manager import get_llm_config, get_app_config, get_paper_processing_config, get_paths_config



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
paths_config = get_paths_config()
app_config = get_app_config()
llm_config = get_llm_config()
paper_config = get_paper_processing_config()

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
                                   original_url: str = None, ai_judgment: dict = None):
    """Save a summary with its service record in JSON format.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        summary_content: The markdown summary content
        tags: Tags dictionary with top and detail tags
        source_type: Either "system" or "user"
        user_id: The user ID who uploaded the paper (if source_type is "user")
        original_url: The original URL of the paper
        ai_judgment: AI judgment data if available
    """
    save_summary_with_service_record_base(
        arxiv_id=arxiv_id,
        summary_content=summary_content,
        tags=tags,
        summary_dir=SUMMARY_DIR,
        source_type=source_type,
        user_id=user_id,
        original_url=original_url,
        ai_judgment=ai_judgment
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

# Load templates
with open(Path(__file__).parent.parent / "ui" / "index.html", "r", encoding="utf-8") as f:
    INDEX_TEMPLATE = f.read()

with open(Path(__file__).parent.parent / "ui" / "detail.html", "r", encoding="utf-8") as f:
    DETAIL_TEMPLATE = f.read()

index_page_module = create_index_page_module(
    summary_dir=SUMMARY_DIR,
    user_service=user_management_module["service"],
    index_template=INDEX_TEMPLATE,
    detail_template=DETAIL_TEMPLATE
)

summary_detail_module = create_summary_detail_module(
    summary_dir=SUMMARY_DIR,
    detail_template=DETAIL_TEMPLATE
)

# Initialize paper submission module
from app.paper_submission.factory import create_paper_submission_module

paper_submission_module = create_paper_submission_module(
    user_data_dir=USER_DATA_DIR,
    data_dir=DATA_DIR,
    summary_dir=SUMMARY_DIR,
    prompts_dir=Path(__file__).parent.parent / "prompts",
    llm_config=llm_config,
    paper_config=paper_config,
    daily_limit=paper_config.daily_submission_limit,
    save_summary_func=save_summary_with_service_record
)

# Register blueprints
app.register_blueprint(user_management_module["blueprint"])
app.register_blueprint(index_page_module["blueprint"])
app.register_blueprint(summary_detail_module["blueprint"])
app.register_blueprint(paper_submission_module["blueprint"])



# -----------------------------------------------------------------------------
# Admin helpers
# -----------------------------------------------------------------------------






# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

# Event tracking functions are now handled by the decoupled EventTracker class
# This function is kept for backward compatibility but delegates to the tracker
def append_event(uid: str, event_type: str, arxiv_id: str | None = None, meta: dict | None = None, ts: str | None = None):
    """Append a single analytics event for the user (backward compatibility).

    This function is now a wrapper around the decoupled EventTracker.
    """
    from .event_tracking.event_tracker import EventTracker
    tracker = EventTracker(USER_DATA_DIR)
    tracker.track_event(uid, event_type, arxiv_id, meta, ts)

# -----------------------------------------------------------------------------
# Event Tracking System
# -----------------------------------------------------------------------------

# Register event tracking blueprint
from .event_tracking.routes import create_event_tracking_blueprint
event_tracking_bp = create_event_tracking_blueprint(USER_DATA_DIR)
app.register_blueprint(event_tracking_bp)

# -----------------------------------------------------------------------------
# Templates (plain strings — no Python f-strings)                               
# -----------------------------------------------------------------------------

BASE_CSS = open(os.path.join('ui', 'base.css'), 'r', encoding='utf-8').read()

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
    return Response(BASE_CSS, mimetype="text/css")

# Unified static file routes for consistent url_for usage
@app.get("/static/css/<path:filename>")
def static_css(filename):
    """Serve CSS files from the ui/css directory."""
    return send_from_directory('../ui/css', filename, mimetype="text/css")


@app.get("/static/js/<path:filename>")
def static_js(filename):
    """Serve JavaScript files from the ui/js directory."""
    return send_from_directory('../ui/js', filename, mimetype="application/javascript")


@app.get("/static/favicon.svg")
def static_favicon_svg():
    """Serve the static SVG favicon file."""
    return send_from_directory('../ui', 'favicon.svg', mimetype="image/svg+xml")


@app.get("/static/favicon.ico")
def static_favicon_ico():
    """Serve the static ICO favicon file, fallback to SVG if ICO not available."""
    ico_path = Path('../ui') / 'favicon.ico'
    if ico_path.exists() and ico_path.stat().st_size > 0:
        return send_from_directory('../ui', 'favicon.ico', mimetype="image/x-icon")
    else:
        # Fallback to SVG if ICO file doesn't exist or is empty
        return send_from_directory('../ui', 'favicon.svg', mimetype="image/svg+xml")


# Event tracking routes are now handled by the decoupled event tracking system
# The /event endpoint is registered via the event tracking blueprint


@app.route("/admin/fetch_latest", methods=["POST"])
def admin_fetch_latest():
    """Admin route to fetch latest summaries from RSS feed."""
    # Debug logging
    print(f"DEBUG: Admin fetch_latest called from {request.remote_addr}")
    print(f"DEBUG: Request headers: {dict(request.headers)}")
    print(f"DEBUG: Request path: {request.path}")
    print(f"DEBUG: Request url: {request.url}")
    
    uid = user_management_module["service"].get_current_user_id()
    if not uid:
        return jsonify({"error": "no-uid"}), 400
    
    if not user_management_module["service"].is_admin_user(uid):
        return jsonify({"error": "unauthorized"}), 403
    
    try:
        # Command execution
        import shutil
        
        # Check if uv is available, fallback to python if not
        uv_path = shutil.which("uv")
        python_path = shutil.which("python")
        
        if not python_path:
            python_path = shutil.which("python3")
        
        if not python_path:
            return jsonify({
                "status": "error",
                "message": "Python not found in PATH"
            }), 500
        
        # Build command - prefer uv if available
        if uv_path:
            cmd = ["uv", "run", "python", "feed_paper_summarizer_service.py", "https://papers.takara.ai/api/feed"]
        else:
            cmd = [python_path, "feed_paper_summarizer_service.py", "https://papers.takara.ai/api/feed"]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=Path(__file__).parent,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode == 0:
            # Clear the cache to force refresh of entries
            index_page_module["scanner"]._cache = {
                "meta": None,
                "count": 0,
                "latest_mtime": 0.0,
            }
            
            # Process the output to extract key information
            stdout_lines = result.stdout.strip().split('\n') if result.stdout else []
            
            # Extract summary statistics
            summary_stats = {}
            for line in stdout_lines:
                if "Found" in line and "paper" in line.lower():
                    summary_stats["papers_found"] = line.strip()
                elif "successfully" in line.lower():
                    summary_stats["success_count"] = line.strip()
                elif "RSS feed updated" in line:
                    summary_stats["rss_updated"] = line.strip()
                elif "All done" in line:
                    summary_stats["completion"] = line.strip()
            
            return jsonify({
                "status": "success",
                "message": "Latest summaries fetched successfully",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary_stats": summary_stats,
                "return_code": result.returncode
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Feed service failed with return code {result.returncode}",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "error",
            "message": "Feed service timed out after 5 minutes"
        }), 500
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": f"Failed to run feed service: {str(exc)}"
        }), 500


@app.route("/admin/fetch_latest_stream", methods=["POST"])
def admin_fetch_latest_stream():
    """Admin route to stream the feed service output in real-time."""
    # Debug logging
    print(f"DEBUG: Admin fetch_latest_stream called from {request.remote_addr}")
    print(f"DEBUG: Request headers: {dict(request.headers)}")
    print(f"DEBUG: Request path: {request.path}")
    print(f"DEBUG: Request url: {request.url}")
    
    uid = user_management_module["service"].get_current_user_id()
    if not uid:
        return jsonify({"error": "no-uid"}), 400
    
    if not user_management_module["service"].is_admin_user(uid):
        return jsonify({"error": "unauthorized"}), 403
    
    def generate():
        try:
            # Send initial status
            yield "data: {\"type\": \"status\", \"message\": \"正在启动服务...\", \"icon\": \"⏳\"}\n\n"
            
            # Command execution
            import shutil
            
            # Check if uv is available, fallback to python if not
            uv_path = shutil.which("uv")
            python_path = shutil.which("python")
            
            if not python_path:
                python_path = shutil.which("python3")
            
            if not python_path:
                yield "data: {\"type\": \"error\", \"message\": \"Python not found in PATH\"}\n\n"
                yield "data: {\"type\": \"complete\", \"status\": \"error\", \"message\": \"Python环境未配置\"}\n\n"
                return
            
            # Build command - prefer uv if available
            if uv_path:
                cmd = ["uv", "run", "python", "feed_paper_summarizer_service.py", "https://papers.takara.ai/api/feed"]
            else:
                cmd = [python_path, "feed_paper_summarizer_service.py", "https://papers.takara.ai/api/feed"]
            
            yield f"data: {{\"type\": \"log\", \"message\": \"执行命令: {' '.join(cmd)}\", \"level\": \"info\"}}\n\n"
            
            # Use Popen to get real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stdout and stderr
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                cwd=Path(__file__).parent
            )
            
            # Send status update
            yield "data: {\"type\": \"status\", \"message\": \"正在连接RSS源...\", \"icon\": \"🔗\"}\n\n"
            
            # Stream output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Clean and sanitize output
                    clean_output = output.rstrip()  # Remove trailing newline only
                    if clean_output:
                        # Remove all control characters that break JSON
                        clean_output = ''.join(char for char in clean_output if char in string.printable)
                        
                        # Escape only the essential characters for JSON
                        clean_output = clean_output.replace('\\', '\\\\').replace('"', '\\"')
                        
                        # Limit line length to prevent overwhelming the frontend
                        if len(clean_output) > 500:
                            clean_output = clean_output[:500] + "... [truncated]"
                        
                        yield f"data: {{\"type\": \"log\", \"message\": \"{clean_output}\", \"level\": \"info\"}}\n\n"
            
            # Wait for process to complete and get return code
            return_code = process.poll()
            
            # Send completion status
            if return_code == 0:
                yield "data: {\"type\": \"status\", \"message\": \"获取成功！\", \"icon\": \"✅\"}\n\n"
                yield "data: {\"type\": \"complete\", \"status\": \"success\", \"message\": \"最新论文摘要获取成功！\"}\n\n"
                
                # Clear the cache to force refresh of entries
                index_page_module["scanner"]._cache = {
                    "meta": None,
                    "count": 0,
                    "latest_mtime": 0.0,
                }
            else:
                yield f"data: {{\"type\": \"log\", \"message\": \"进程返回码: {return_code}\", \"level\": \"error\"}}\n\n"
                yield "data: {\"type\": \"status\", \"message\": \"获取失败\", \"icon\": \"❌\"}\n\n"
                yield "data: {\"type\": \"complete\", \"status\": \"error\", \"message\": f\"Feed service failed with return code {return_code}\"}\n\n"
                
        except FileNotFoundError as e:
            error_msg = f"文件未找到: {str(e)}"
            yield f"data: {{\"type\": \"error\", \"message\": \"{error_msg}\"}}\n\n"
            yield "data: {\"type\": \"complete\", \"status\": \"error\", \"message\": \"文件路径错误\"}\n\n"
        except PermissionError as e:
            error_msg = f"权限错误: {str(e)}"
            yield f"data: {{\"type\": \"error\", \"message\": \"{error_msg}\"}}\n\n"
            yield "data: {\"type\": \"complete\", \"status\": \"error\", \"message\": \"权限不足\"}\n\n"
        except Exception as exc:
            error_msg = f"执行过程中发生错误: {str(exc)}"
            yield f"data: {{\"type\": \"error\", \"message\": \"{error_msg}\"}}\n\n"
            yield "data: {\"type\": \"complete\", \"status\": \"error\", \"message\": \"执行失败\"}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


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