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

# Register paper submission blueprint
app.register_blueprint(paper_submission_module["blueprint"])



# -----------------------------------------------------------------------------
# Admin helpers
# -----------------------------------------------------------------------------

def is_admin_user(uid: str) -> bool:
    """Check if the user is an admin based on configuration."""
    return uid.strip() in app_config.admin_user_ids




# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def render_markdown(md_text: str) -> str:
    """Convert Markdown → HTML (GitHub-flavoured-ish)."""
    return markdown.markdown(
        md_text,
        extensions=[
            "fenced_code",
            "tables",
            "codehilite",
            "toc",
            "attr_list",
        ],
    )


_ENTRIES_CACHE: dict = {
    "meta": None,           # list of dicts without preview_html
    "count": 0,
    "latest_mtime": 0.0,    # max mtime among md/tag files
}


def _scan_entries_meta() -> list[dict]:
    """Scan summary directory and build metadata for all entries (no HTML).

    Returns a list of dicts with keys: id, updated, tags, top_tags, detail_tags, source_type, user_id.
    This function also maintains a lightweight cache to avoid re-reading files
    on every request when nothing changed.
    """
    # Get all .json files (new format) and .md files (legacy format)
    json_files = list(SUMMARY_DIR.glob("*.json"))
    md_files = list(SUMMARY_DIR.glob("*.md"))
    
    # Filter out .tags.json files from json_files
    json_files = [f for f in json_files if not f.name.endswith('.tags.json')]
    
    # Count total files for cache invalidation
    count = len(json_files) + len(md_files)
    
    # Compute latest mtime considering all relevant files
    latest_mtime = 0.0
    for p in json_files + md_files:
        try:
            latest_mtime = max(latest_mtime, p.stat().st_mtime)
        except Exception:
            continue

    if (
        _ENTRIES_CACHE.get("meta") is not None
        and _ENTRIES_CACHE.get("count") == count
        and float(_ENTRIES_CACHE.get("latest_mtime") or 0.0) >= float(latest_mtime)
    ):
        return list(_ENTRIES_CACHE["meta"])  # type: ignore[index]

    entries_meta: list[dict] = []
    processed_ids = set()
    
    # Process new JSON format files first
    for json_path in json_files:
        try:
            arxiv_id = json_path.stem
            if arxiv_id in processed_ids:
                continue
                
            data = json.loads(json_path.read_text(encoding="utf-8"))
            service_data = data.get("service_data", {})
            summary_data = data.get("summary_data", {})
            
            # Parse tags
            tags: list[str] = []
            top_tags: list[str] = []
            detail_tags: list[str] = []
            
            tags_dict = summary_data.get("tags", {})
            if isinstance(tags_dict, dict):
                if isinstance(tags_dict.get("top"), list):
                    top_tags = [str(t).strip().lower() for t in tags_dict.get("top") if str(t).strip()]
                if isinstance(tags_dict.get("tags"), list):
                    detail_tags = [str(t).strip().lower() for t in tags_dict.get("tags") if str(t).strip()]
            tags = (top_tags or []) + (detail_tags or [])
            
            # Parse updated time
            updated_str = summary_data.get("updated_at")
            if updated_str:
                try:
                    updated = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                except Exception:
                    updated = datetime.fromtimestamp(json_path.stat().st_mtime)
            else:
                updated = datetime.fromtimestamp(json_path.stat().st_mtime)
            
            entries_meta.append({
                "id": arxiv_id,
                "updated": updated,
                "tags": tags,
                "top_tags": top_tags,
                "detail_tags": detail_tags,
                "source_type": service_data.get("source_type", "system"),
                "user_id": service_data.get("user_id"),
                "original_url": service_data.get("original_url"),
            })
            processed_ids.add(arxiv_id)
        except Exception as e:
            print(f"Error processing JSON file {json_path}: {e}")
            continue
    
    # Process legacy .md files
    for md_path in md_files:
        try:
            arxiv_id = md_path.stem
            if arxiv_id in processed_ids:
                continue
                
            stat = md_path.stat()
            updated = datetime.fromtimestamp(stat.st_mtime)

            # Load tags from legacy .tags.json file
            tags: list[str] = []
            top_tags: list[str] = []
            detail_tags: list[str] = []
            tags_file = md_path.with_suffix("")
            tags_file = tags_file.with_name(tags_file.name + ".tags.json")
            try:
                if tags_file.exists():
                    data = json.loads(tags_file.read_text(encoding="utf-8"))
                    # support legacy [..], flat {"top": [...], "tags": [...]},
                    # and nested {"tags": {"top": [...], "tags": [...]}}
                    if isinstance(data, list):
                        detail_tags = [str(t).strip().lower() for t in data if str(t).strip()]
                    elif isinstance(data, dict):
                        container = data
                        if isinstance(data.get("tags"), dict):
                            container = data.get("tags") or {}
                        if isinstance(container.get("top"), list):
                            top_tags = [str(t).strip().lower() for t in container.get("top") if str(t).strip()]
                        if isinstance(container.get("tags"), list):
                            detail_tags = [str(t).strip().lower() for t in container.get("tags") if str(t).strip()]
                    tags = (top_tags or []) + (detail_tags or [])
            except Exception:
                tags = []

            entries_meta.append({
                "id": arxiv_id,
                "updated": updated,
                "tags": tags,
                "top_tags": top_tags,
                "detail_tags": detail_tags,
                "source_type": "system",  # Legacy files default to system
                "user_id": None,
                "original_url": None,
            })
            processed_ids.add(arxiv_id)
        except Exception as e:
            print(f"Error processing legacy MD file {md_path}: {e}")
            continue

    entries_meta.sort(key=lambda e: e["updated"], reverse=True)
    _ENTRIES_CACHE["meta"] = list(entries_meta)
    _ENTRIES_CACHE["count"] = count
    _ENTRIES_CACHE["latest_mtime"] = latest_mtime
    return entries_meta


def _render_page_entries(entries_meta: list[dict]) -> list[dict]:
    """Given a slice of entries meta, materialize preview_html for each."""
    rendered: list[dict] = []
    for meta in entries_meta:
        try:
            # Try to load from new JSON format first
            json_path = SUMMARY_DIR / f"{meta['id']}.json"
            if json_path.exists():
                data = json.loads(json_path.read_text(encoding="utf-8"))
                summary_data = data.get("summary_data", {})
                md_text = summary_data.get("content", "")
            else:
                # Fallback to legacy .md file
                md_path = SUMMARY_DIR / f"{meta['id']}.md"
                md_text = md_path.read_text(encoding="utf-8", errors="ignore")
            
            preview_html = render_markdown(md_text)
        except Exception:
            preview_html = ""
        item = dict(meta)
        item["preview_html"] = preview_html
        rendered.append(item)
    return rendered



# ------------------------- user-state helpers ---------------------------------

def _user_file(uid: str) -> Path:
    return USER_DATA_DIR / f"{uid}.json"


def load_user_data(uid: str) -> dict:
    """Load full user data structure with backward compatibility.

    Shape:
    {
      "read": {arxiv_id: "YYYY-MM-DD" | null, ...},
      "events": [ {"ts": ISO8601, "type": str, "arxiv_id": str|None, "meta": dict|None, "path": str|None, "ua": str|None}, ... ]
    }
    """
    try:
        data = json.loads(_user_file(uid).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    # migrate legacy list-based read
    raw_read = data.get("read", {})
    if isinstance(raw_read, list):
        read_map = {str(rid): None for rid in raw_read}
    elif isinstance(raw_read, dict):
        read_map = {str(k): v for k, v in raw_read.items()}
    else:
        read_map = {}

    events = data.get("events")
    if not isinstance(events, list):
        events = []

    return {"read": read_map, "events": events}


def load_read_map(uid: str) -> dict[str, str | None]:
    data = load_user_data(uid)
    return data.get("read", {})


def save_user_data(uid: str, data: dict) -> None:
    _user_file(uid).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_read_map(uid: str, read_map: dict[str, str | None]):
    """Persist read map, preserving other fields (like events)."""
    data = load_user_data(uid)
    data["read"] = read_map
    save_user_data(uid, data)


def append_event(uid: str, event_type: str, arxiv_id: str | None = None, meta: dict | None = None, ts: str | None = None):
    """Append a single analytics event for the user.

    If ts is provided (ISO 8601, preferably with timezone offset), it will be
    used. Otherwise, we store the server local timezone timestamp with offset.
    """
    data = load_user_data(uid)
    evt = {
        "ts": ts or datetime.now().astimezone().isoformat(timespec="seconds"),
        "type": event_type,
        "arxiv_id": arxiv_id,
        "meta": meta or {},
        "path": request.path if request else None,
        "ua": request.headers.get("User-Agent") if request else None,
    }
    data.setdefault("events", []).append(evt)
    save_user_data(uid, data)

# -----------------------------------------------------------------------------
# Templates (plain strings — no Python f-strings)                               
# -----------------------------------------------------------------------------

BASE_CSS = open(os.path.join('ui', 'base.css'), 'r', encoding='utf-8').read()

INDEX_TEMPLATE = open(os.path.join('ui', 'index.html'), 'r', encoding='utf-8').read()
DETAIL_TEMPLATE = open(os.path.join('ui', 'detail.html'), 'r', encoding='utf-8').read()

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

@app.route("/", methods=["GET"])
def index():
    uid = request.cookies.get("uid")
    entries_meta = _scan_entries_meta()
    # tag filtering (from query string)
    active_tag = (request.args.get("tag") or "").strip().lower() or None
    tag_query = (request.args.get("q") or "").strip().lower()
    # support multiple top filters: ?top=llm&top=cv
    active_tops = [t.strip().lower() for t in request.args.getlist("top") if t.strip()]
    unread_count = None
    read_total = None
    read_today = None
    if uid:
        read_map = load_read_map(uid)
        read_ids = set(read_map.keys())
        unread_count = len([e for e in entries_meta if e["id"] not in read_ids])
        entries_meta = [e for e in entries_meta if e["id"] not in read_ids]
        read_total = len(read_ids)
        # Count how many read today, based on stored per-paper read date/time (YYYY-MM-DD[THH:MM:SS])
        today_iso = date.today().isoformat()
        read_today = 0
        for d in read_map.values():
            if not d:
                continue
            try:
                # match date prefix for both date-only and datetime strings
                if str(d).split('T', 1)[0] == today_iso:
                    read_today += 1
            except Exception:
                continue
    # apply tag-based filters if present
    if active_tag:
        entries_meta = [e for e in entries_meta if active_tag in (e.get("detail_tags") or []) or active_tag in (e.get("top_tags") or [])]
    if tag_query:
        def matches_query(tags: list[str] | None, query: str) -> bool:
            if not tags:
                return False
            for t in tags:
                if query in t:
                    return True
            return False
        entries_meta = [e for e in entries_meta if matches_query(e.get("detail_tags"), tag_query) or matches_query(e.get("top_tags"), tag_query)]
    if active_tops:
        entries_meta = [e for e in entries_meta if any(t in (e.get("top_tags") or []) for t in active_tops)]

    # compute tag cloud from filtered entries only (meta only, no HTML work)
    tag_counts: dict[str, int] = {}
    top_counts: dict[str, int] = {}
    for e in entries_meta:
        for t in e.get("detail_tags", []) or []:
            tag_counts[t] = tag_counts.get(t, 0) + 1
        for t in e.get("top_tags", []) or []:
            top_counts[t] = top_counts.get(t, 0) + 1

    # sort tags by frequency then name
    tag_cloud = sorted(
        ({"name": k, "count": v} for k, v in tag_counts.items()),
        key=lambda item: (-item["count"], item["name"]),
    )
    top_cloud = sorted(
        ({"name": k, "count": v} for k, v in top_counts.items()),
        key=lambda item: (-item["count"], item["name"]),
    )

    # when searching, show only related detailed tags in the filter bar
    if tag_query:
        tag_cloud = [t for t in tag_cloud if tag_query in t["name"]]

    # pagination
    try:
        page = max(1, int(request.args.get("page", 1)))
    except Exception:
        page = 1
    try:
        per_page = int(request.args.get("per_page", 10))
    except Exception:
        per_page = 10
    per_page = max(1, min(per_page, 30))
    total_items = len(entries_meta)
    total_pages = max(1, math.ceil(total_items / per_page))
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    page_entries = entries_meta[start:end]

    # materialize preview HTML only for current page
    entries = _render_page_entries(page_entries)

    # Get admin users list for template
    admin_users = [admin_id.strip() for admin_id in os.getenv("ADMIN_USER_IDS", "").split(",") if admin_id.strip()]

    resp = make_response(
        render_template_string(
            INDEX_TEMPLATE,
            entries=entries,
            uid=uid,
            unread_count=unread_count,
            read_total=read_total,
            read_today=read_today,
            tag_cloud=tag_cloud,
            active_tag=active_tag,
            top_cloud=top_cloud,
            active_tops=active_tops,
            tag_query=tag_query,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_items=total_items,
            admin_users=admin_users,
            # Add admin URLs for JavaScript
            admin_fetch_url=url_for("admin_fetch_latest"),
            admin_stream_url=url_for("admin_fetch_latest_stream"),
            # Add other API URLs for JavaScript
            mark_read_url=url_for("mark_read", arxiv_id="__ID__").replace("__ID__", ""),
            unmark_read_url=url_for("unmark_read", arxiv_id="__ID__").replace("__ID__", ""),
            reset_url=url_for("reset_read"),
        )
    )
    return resp


@app.route("/set_user", methods=["POST"])
def set_user():
    uid = request.form.get("uid", "").strip()
    if not uid:
        return redirect(url_for("index"))
    resp = make_response(redirect(url_for("index")))
    resp.set_cookie("uid", uid, max_age=60 * 60 * 24 * 365 * 3)  # 3-year cookie
    return resp


@app.route("/mark_read/<arxiv_id>", methods=["POST"])
def mark_read(arxiv_id):
    uid = request.cookies.get("uid")
    if not uid:
        return jsonify({"error": "no-uid"}), 400
    read_map = load_read_map(uid)
    # store local date-time with timezone offset for more precise analytics
    read_map[str(arxiv_id)] = datetime.now().astimezone().isoformat(timespec="seconds")
    save_read_map(uid, read_map)
    return jsonify({"status": "ok"})


@app.route("/unmark_read/<arxiv_id>", methods=["POST"])
def unmark_read(arxiv_id):
    uid = request.cookies.get("uid")
    if not uid:
        return jsonify({"error": "no-uid"}), 400
    read_map = load_read_map(uid)
    read_map.pop(str(arxiv_id), None)
    save_read_map(uid, read_map)
    return jsonify({"status": "ok"})


@app.route("/reset", methods=["POST"])
def reset_read():
    uid = request.cookies.get("uid")
    if not uid:
        return jsonify({"error": "no-uid"}), 400
    try:
        _user_file(uid).unlink(missing_ok=True)
    except Exception:
        pass
    return jsonify({"status": "reset"})


@app.route("/summary/<arxiv_id>")
def view_summary(arxiv_id):
    # Try to load from new JSON format first
    record = load_summary_with_service_record(arxiv_id)
    if not record:
        abort(404)
    
    summary_data = record["summary_data"]
    service_data = record["service_data"]
    
    html_content = render_markdown(summary_data["content"])
    uid = request.cookies.get("uid")
    
    # Extract tags
    tags: list[str] = []
    tags_dict = summary_data.get("tags", {})
    if isinstance(tags_dict, dict):
        raw = []
        if isinstance(tags_dict.get("top"), list):
            raw.extend(tags_dict.get("top") or [])
        if isinstance(tags_dict.get("tags"), list):
            raw.extend(tags_dict.get("tags") or [])
        tags = [str(t).strip().lower() for t in raw if str(t).strip()]
    
    return render_template_string(
        DETAIL_TEMPLATE, 
        content=html_content, 
        arxiv_id=arxiv_id, 
        tags=tags,
        source_type=service_data.get("source_type", "system"),
        user_id=service_data.get("user_id"),
        original_url=service_data.get("original_url")
    )

@app.route("/read")
def read_papers():
    uid = request.cookies.get("uid")
    if not uid:
        return redirect(url_for("index"))
    read_map = load_read_map(uid)
    entries_meta = _scan_entries_meta()
    read_entries_meta = [e for e in entries_meta if e["id"] in set(read_map.keys())]
    # allow optional tag filter on read list
    active_tag = (request.args.get("tag") or "").strip().lower() or None
    tag_query = (request.args.get("q") or "").strip().lower()
    if active_tag:
        read_entries_meta = [e for e in read_entries_meta if active_tag in (e.get("tags") or []) or active_tag in (e.get("top_tags") or [])]
    if tag_query:
        def matches_query(tags: list[str] | None, query: str) -> bool:
            if not tags:
                return False
            for t in tags:
                if query in t:
                    return True
            return False
        read_entries_meta = [e for e in read_entries_meta if matches_query(e.get("tags"), tag_query)]
    # tag cloud for read entries
    tag_counts: dict[str, int] = {}
    for e in read_entries_meta:
        for t in (e.get("tags", []) or []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    tag_cloud = sorted(
        ({"name": k, "count": v} for k, v in tag_counts.items()),
        key=lambda item: (-item["count"], item["name"]),
    )
    # pagination for read list
    try:
        page = max(1, int(request.args.get("page", 1)))
    except Exception:
        page = 1
    try:
        per_page = int(request.args.get("per_page", 10))
    except Exception:
        per_page = 10
    per_page = max(1, min(per_page, 100))
    total_items = len(read_entries_meta)
    total_pages = max(1, math.ceil(total_items / per_page))
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    page_entries = read_entries_meta[start:end]

    # render only the current page
    entries = _render_page_entries(page_entries)
    
    # Get admin users list for template
    admin_users = [admin_id.strip() for admin_id in os.getenv("ADMIN_USER_IDS", "").split(",") if admin_id.strip()]
    
    return render_template_string(
        INDEX_TEMPLATE,
        entries=entries,
        uid=uid,
        unread_count=None,
        read_total=None,
        read_today=None,
        show_read=True,
        tag_cloud=tag_cloud,
        active_tag=active_tag,
        tag_query=tag_query,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_items=total_items,
        admin_users=admin_users,
        # Add admin URLs for JavaScript
        admin_fetch_url=url_for("admin_fetch_latest"),
        admin_stream_url=url_for("admin_fetch_latest_stream"),
        # Add other API URLs for JavaScript
        mark_read_url=url_for("mark_read", arxiv_id="__ID__").replace("__ID__", ""),
        unmark_read_url=url_for("unmark_read", arxiv_id="__ID__").replace("__ID__", ""),
        reset_url=url_for("reset_read"),
    )

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





@app.route("/event", methods=["POST"])
def ingest_event():
    uid = request.cookies.get("uid")
    if not uid:
        return jsonify({"error": "no-uid"}), 400
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            raw = request.get_data(as_text=True) or "{}"
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {}
        etype = str(payload.get("type", "")).strip()
        arxiv_id = payload.get("arxiv_id")
        meta = payload.get("meta") or {}
        ts_client = payload.get("ts")
        tz_off_min = payload.get("tz_offset_min")  # minutes where UTC - local
        # keep only click events
        allowed = {"mark_read", "unmark_read", "open_pdf", "login", "logout", "reset", "read_list", "read_more"}
        if etype in allowed:
            ts_local: str | None = None
            try:
                if ts_client:
                    # parse client ts and adjust to local timezone if offset provided
                    # accept 'Z' by replacing with +00:00
                    dt_utc = datetime.fromisoformat(str(ts_client).replace('Z', '+00:00'))
                    if isinstance(tz_off_min, int):
                        tz = timezone(timedelta(minutes=-tz_off_min))
                        dt_local = dt_utc.astimezone(tz)
                        ts_local = dt_local.isoformat(timespec="seconds")
                    else:
                        ts_local = dt_utc.astimezone().isoformat(timespec="seconds")
            except Exception:
                ts_local = None
            append_event(
                uid,
                etype,
                arxiv_id=str(arxiv_id) if arxiv_id else None,
                meta=meta,
                ts=ts_local,
            )
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/admin/fetch_latest", methods=["POST"])
def admin_fetch_latest():
    """Admin route to fetch latest summaries from RSS feed."""
    # Debug logging
    print(f"DEBUG: Admin fetch_latest called from {request.remote_addr}")
    print(f"DEBUG: Request headers: {dict(request.headers)}")
    print(f"DEBUG: Request path: {request.path}")
    print(f"DEBUG: Request url: {request.url}")
    
    uid = request.cookies.get("uid")
    if not uid:
        return jsonify({"error": "no-uid"}), 400
    
    if not is_admin_user(uid):
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
            global _ENTRIES_CACHE
            _ENTRIES_CACHE = {
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
    
    uid = request.cookies.get("uid")
    if not uid:
        return jsonify({"error": "no-uid"}), 400
    
    if not is_admin_user(uid):
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
                global _ENTRIES_CACHE
                _ENTRIES_CACHE = {
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