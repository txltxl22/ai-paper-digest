import os
import json
import subprocess
import re
import string
from pathlib import Path
from datetime import datetime, date, timezone, timedelta

# Import configuration management
from config_manager import get_llm_config, get_app_config, get_paper_processing_config, get_paths_config

# Windows-specific environment setup
if os.name == 'nt':  # Windows
    # Set UTF-8 encoding for Windows
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # Ensure proper path handling
    os.environ['PYTHONPATH'] = str(Path(__file__).parent)
    # Set console encoding to UTF-8 if possible
    try:
        import codecs
        import sys
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

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

app = Flask(__name__)
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
SUMMARY_DIR = Path(__file__).parent / paths_config.summary_dir
USER_DATA_DIR = Path(__file__).parent / paths_config.user_data_dir
PDF_DIR = Path(__file__).parent / paths_config.papers_dir
MD_DIR = Path(__file__).parent / paths_config.markdown_dir
DATA_DIR = Path(__file__).parent / "data"

# Create directories
SUMMARY_DIR.mkdir(exist_ok=True)
USER_DATA_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
MD_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# Service Record Management
# -----------------------------------------------------------------------------

def create_service_record(arxiv_id: str, source_type: str = "system", user_id: str = None, 
                         original_url: str = None, ai_judgment: dict = None) -> dict:
    """Create a service record for a paper summary.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        source_type: Either "system" (from background processing) or "user" (user upload)
        user_id: The user ID who uploaded the paper (if source_type is "user")
        original_url: The original URL of the paper
        ai_judgment: AI judgment data if available
    
    Returns:
        Service record dictionary
    """
    record = {
        "service_data": {
            "arxiv_id": arxiv_id,
            "source_type": source_type,  # "system" or "user"
            "created_at": datetime.now().isoformat(),
            "original_url": original_url,
            "ai_judgment": ai_judgment or {}
        }
    }
    
    if source_type == "user" and user_id:
        record["service_data"]["user_id"] = user_id
    
    return record

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
    # Create the combined record
    record = create_service_record(arxiv_id, source_type, user_id, original_url, ai_judgment)
    record["summary_data"] = {
        "content": summary_content,
        "tags": tags,
        "updated_at": datetime.now().isoformat()
    }
    
    # Save as JSON file
    json_path = SUMMARY_DIR / f"{arxiv_id}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    
    # Also save the legacy .md and .tags.json files for backward compatibility
    md_path = SUMMARY_DIR / f"{arxiv_id}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(summary_content)
    
    tags_path = SUMMARY_DIR / f"{arxiv_id}.tags.json"
    with open(tags_path, 'w', encoding='utf-8') as f:
        json.dump(tags, f, ensure_ascii=False, indent=2)

def load_summary_with_service_record(arxiv_id: str) -> dict:
    """Load a summary with its service record.
    
    Args:
        arxiv_id: The arXiv ID of the paper
    
    Returns:
        Dictionary containing service_data and summary_data, or None if not found
    """
    json_path = SUMMARY_DIR / f"{arxiv_id}.json"
    if json_path.exists():
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading service record for {arxiv_id}: {e}")
    
    # Fallback to legacy format
    return load_legacy_summary(arxiv_id)

def load_legacy_summary(arxiv_id: str) -> dict:
    """Load a summary in legacy format (separate .md and .tags.json files).
    
    Args:
        arxiv_id: The arXiv ID of the paper
    
    Returns:
        Dictionary with service_data and summary_data, defaulting to system source
    """
    md_path = SUMMARY_DIR / f"{arxiv_id}.md"
    tags_path = SUMMARY_DIR / f"{arxiv_id}.tags.json"
    
    if not md_path.exists():
        return None
    
    try:
        # Load summary content
        summary_content = md_path.read_text(encoding='utf-8')
        
        # Load tags
        tags = {"top": [], "tags": []}
        if tags_path.exists():
            try:
                tags = json.loads(tags_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        
        # Create service record with default system source
        service_record = create_service_record(arxiv_id, "system")
        
        return {
            "service_data": service_record["service_data"],
            "summary_data": {
                "content": summary_content,
                "tags": tags,
                "updated_at": datetime.fromtimestamp(md_path.stat().st_mtime).isoformat()
            }
        }
    except Exception as e:
        print(f"Error loading legacy summary for {arxiv_id}: {e}")
        return None

def migrate_legacy_summaries_to_service_record() -> dict:
    """Migrate all legacy summaries (.md + .tags.json) to new service record format.
    
    This function scans for legacy format summaries and creates service records for them
    with update times based on the file creation time.
    
    Returns:
        Dictionary with migration statistics
    """
    import os
    from pathlib import Path
    
    migration_stats = {
        "total_legacy_files": 0,
        "migrated": 0,
        "skipped": 0,
        "errors": 0,
        "details": []
    }
    
    # Find all .md files that don't have corresponding .json files
    md_files = list(SUMMARY_DIR.glob("*.md"))
    
    for md_path in md_files:
        arxiv_id = md_path.stem
        json_path = SUMMARY_DIR / f"{arxiv_id}.json"
        
        # Skip if service record already exists
        if json_path.exists():
            migration_stats["skipped"] += 1
            migration_stats["details"].append({
                "arxiv_id": arxiv_id,
                "status": "skipped",
                "reason": "service record already exists"
            })
            continue
        
        migration_stats["total_legacy_files"] += 1
        
        try:
            # Load summary content
            summary_content = md_path.read_text(encoding="utf-8")
            
            # Load tags if available
            tags_path = SUMMARY_DIR / f"{arxiv_id}.tags.json"
            tags = {"top": [], "tags": []}
            if tags_path.exists():
                try:
                    tags = json.loads(tags_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            
            # Create service record with file creation time as update time
            service_record = create_service_record(arxiv_id, "system")
            
            # Use file creation time for updated_at
            file_creation_time = datetime.fromtimestamp(md_path.stat().st_mtime)
            
            record = {
                "service_data": service_record["service_data"],
                "summary_data": {
                    "content": summary_content,
                    "tags": tags,
                    "updated_at": file_creation_time.isoformat()
                }
            }
            
            # Save the new service record
            json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            
            migration_stats["migrated"] += 1
            migration_stats["details"].append({
                "arxiv_id": arxiv_id,
                "status": "migrated",
                "update_time": file_creation_time.isoformat()
            })
            
        except Exception as e:
            migration_stats["errors"] += 1
            migration_stats["details"].append({
                "arxiv_id": arxiv_id,
                "status": "error",
                "error": str(e)
            })
    
    return migration_stats

# -----------------------------------------------------------------------------
# Admin helpers
# -----------------------------------------------------------------------------

def is_admin_user(uid: str) -> bool:
    """Check if the user is an admin based on configuration."""
    return uid.strip() in app_config.admin_user_ids


def is_windows_system() -> bool:
    """Check if the system is running Windows."""
    return os.name == 'nt'

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
BADGE_CSS = open(os.path.join('ui', 'css', 'badges.css'), 'r', encoding='utf-8').read()
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


@app.route("/raw/<arxiv_id>.md")
def raw_markdown(arxiv_id):
    md_path = SUMMARY_DIR / f"{arxiv_id}.md"
    if not md_path.exists():
        abort(404)
    return send_from_directory(md_path.parent, md_path.name, mimetype="text/markdown")


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

@app.get("/assets/badges.css")
def badge_css():
    return Response(BADGE_CSS, mimetype="text/css")


@app.get("/favicon.svg")
def favicon_svg():
    svg = (
        """
<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"64\" height=\"64\" viewBox=\"0 0 64 64\">
  <defs>
    <linearGradient id=\"gLight\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\">
      <stop offset=\"0%\" stop-color=\"#6366f1\"/>
      <stop offset=\"100%\" stop-color=\"#22d3ee\"/>
    </linearGradient>
    <linearGradient id=\"gDark\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\">
      <stop offset=\"0%\" stop-color=\"#1d4ed8\"/>
      <stop offset=\"100%\" stop-color=\"#06b6d4\"/>
    </linearGradient>
    <filter id=\"shadow\" x=\"-20%\" y=\"-20%\" width=\"140%\" height=\"140%\">
      <feDropShadow dx=\"0\" dy=\"2\" stdDeviation=\"2\" flood-color=\"#000\" flood-opacity=\".25\"/>
    </filter>
  </defs>
  <style>
    :root { color-scheme: light dark; }
    .light-only { display: block; }
    .dark-only { display: none; }
    .fg { fill: #ffffff; }
    .accent { fill: #f59e0b; }
    @media (prefers-color-scheme: dark) {
      .light-only { display: none; }
      .dark-only { display: block; }
      .fg { fill: #f8fafc; }
      .accent { fill: #fbbf24; }
    }
  </style>

  <!-- vivid gradient background, light/dark aware -->
  <rect class=\"light-only\" x=\"4\" y=\"4\" width=\"56\" height=\"56\" rx=\"14\" fill=\"url(#gLight)\"/>
  <rect class=\"dark-only\"  x=\"4\" y=\"4\" width=\"56\" height=\"56\" rx=\"14\" fill=\"url(#gDark)\"/>

  <!-- stylized book with bookmark and spark -->
  <g filter=\"url(#shadow)\">
    <!-- book body -->
    <rect x=\"17\" y=\"16\" width=\"30\" height=\"34\" rx=\"6\" class=\"fg\"/>
    <!-- page lines -->
    <rect x=\"22\" y=\"22\" width=\"20\" height=\"2\" rx=\"1\" opacity=\".25\"/>
    <rect x=\"22\" y=\"28\" width=\"20\" height=\"2\" rx=\"1\" opacity=\".25\"/>
    <rect x=\"22\" y=\"34\" width=\"14\" height=\"2\" rx=\"1\" opacity=\".25\"/>
    <!-- bookmark ribbon -->
    <path class=\"accent\" d=\"M40 16 v18 l-5-3 l-5 3 V16 z\"/>
  </g>

  <!-- spark -->
  <g transform=\"translate(44 44)\">
    <circle r=\"2.5\" class=\"fg\" opacity=\".3\"/>
    <path class=\"fg\" d=\"M0-4 L1.2-1.2 4 0 1.2 1.2 0 4 -1.2 1.2 -4 0 -1.2 -1.2 Z\"/>
  </g>
</svg>
"""
    ).strip()
    return Response(svg, mimetype="image/svg+xml")


@app.get("/favicon.ico")
def favicon_ico():
    # Serve SVG to avoid 404; modern browsers accept the linked SVG favicon.
    # This keeps network quiet even if the user agent auto-requests /favicon.ico.
    return favicon_svg()


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
        # Cross-platform command execution with better Windows support
        import platform
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
        
        # Build command based on available tools and platform
        if uv_path and platform.system() != "Windows":
            # Use uv on Unix-like systems
            cmd = ["uv", "run", "python", "feed_paper_summarizer_service.py", "https://papers.takara.ai/api/feed"]
        else:
            # Fallback to direct python execution, especially for Windows
            cmd = [python_path, "feed_paper_summarizer_service.py", "https://papers.takara.ai/api/feed"]
        
        # Windows-specific subprocess settings
        creation_flags = 0
        if platform.system() == "Windows":
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',  # Explicitly set UTF-8 encoding
            errors='replace',   # Replace problematic characters
            cwd=Path(__file__).parent,
            timeout=300,  # 5 minutes timeout
            creationflags=creation_flags
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
                "return_code": result.returncode,
                "platform": "Windows" if is_windows_system() else "Unix/Linux"
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
            # Send initial status with platform info
            platform_info = "Windows" if is_windows_system() else "Unix/Linux"
            yield f"data: {{\"type\": \"status\", \"message\": \"正在启动服务... ({platform_info})\", \"icon\": \"⏳\"}}\n\n"
            
            # Cross-platform command execution
            import platform
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
            
            # Build command based on available tools
            if uv_path and platform.system() != "Windows":
                # Use uv on Unix-like systems
                cmd = ["uv", "run", "python", "feed_paper_summarizer_service.py", "https://papers.takara.ai/api/feed"]
            else:
                # Fallback to direct python execution
                cmd = [python_path, "feed_paper_summarizer_service.py", "https://papers.takara.ai/api/feed"]
            
            yield f"data: {{\"type\": \"log\", \"message\": \"执行命令: {' '.join(cmd)}\", \"level\": \"info\"}}\n\n"
            
            # Use Popen to get real-time output with better Windows support
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stdout and stderr
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',  # Explicitly set UTF-8 encoding
                errors='replace',   # Replace problematic characters
                cwd=Path(__file__).parent,
                # Windows-specific settings
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            
            # Send status update
            yield "data: {\"type\": \"status\", \"message\": \"正在连接RSS源...\", \"icon\": \"🔗\"}\n\n"
            
            # Stream output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Clean and sanitize output for Windows compatibility
                    clean_output = output.rstrip()  # Remove trailing newline only
                    if clean_output:
                        # Handle Windows encoding issues by replacing problematic characters
                        # Remove or replace emoji and special characters that cause GBK encoding issues
                        clean_output = clean_output.encode('utf-8', errors='replace').decode('utf-8')
                        
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


@app.route("/admin/migrate_legacy_summaries", methods=["POST"])
def admin_migrate_legacy_summaries():
    """Admin route to migrate legacy summaries to service record format."""
    uid = request.cookies.get("uid")
    if not uid:
        return jsonify({"error": "no-uid"}), 400
    
    if not is_admin_user(uid):
        return jsonify({"error": "unauthorized"}), 403
    
    try:
        # Run the migration
        migration_stats = migrate_legacy_summaries_to_service_record()
        
        # Clear the cache to force refresh of entries
        global _ENTRIES_CACHE
        _ENTRIES_CACHE = {
            "meta": None,
            "count": 0,
            "latest_mtime": 0.0,
        }
        
        return jsonify({
            "status": "success",
            "message": "Legacy summaries migration completed",
            "migration_stats": migration_stats
        })
        
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


# -----------------------------------------------------------------------------
# Paper URL submission and processing
# -----------------------------------------------------------------------------

def get_client_ip():
    """Get client IP address, handling proxy headers."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

def check_daily_limit(ip):
    """Check if IP has exceeded daily limit."""
    today = date.today().isoformat()
    limit_file = DATA_DIR / "daily_limits.json"
    
    try:
        if limit_file.exists():
            with open(limit_file, 'r', encoding='utf-8') as f:
                limits = json.load(f)
        else:
            limits = {}
        
        # Clean up old entries
        limits = {k: v for k, v in limits.items() if v['date'] == today}
        
        if ip in limits:
            return limits[ip]['count'] < paper_config.daily_submission_limit
        return True
        
    except Exception:
        return True

def increment_daily_limit(ip):
    """Increment daily limit counter for IP."""
    today = date.today().isoformat()
    limit_file = DATA_DIR / "daily_limits.json"
    
    try:
        if limit_file.exists():
            with open(limit_file, 'r', encoding='utf-8') as f:
                limits = json.load(f)
        else:
            limits = {}
        
        # Clean up old entries
        limits = {k: v for k, v in limits.items() if v['date'] == today}
        
        if ip in limits:
            limits[ip]['count'] += 1
        else:
            limits[ip] = {'date': today, 'count': 1}
        
        with open(limit_file, 'w', encoding='utf-8') as f:
            json.dump(limits, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Error updating daily limit: {e}")


def save_uploaded_url(uid, url, ai_result, process_result):
    """Save uploaded URL information to user data."""
    try:
        user_file = _user_file(uid)
        
        # Load existing user data
        if user_file.exists():
            with open(user_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
        else:
            user_data = {"read": {}, "events": [], "uploaded_urls": []}
        
        # Initialize uploaded_urls section if not exists
        if "uploaded_urls" not in user_data:
            user_data["uploaded_urls"] = []
        
        # Create upload record
        upload_record = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "ai_judgment": {
                "is_ai": ai_result[0],
                "confidence": ai_result[1],
                "tags": ai_result[2] if len(ai_result) > 2 else []
            },
            "process_result": {
                "success": process_result.get("success", False),
                "error": process_result.get("error", None),
                "summary_path": process_result.get("summary_path", None),
                "paper_subject": process_result.get("paper_subject", None)
            }
        }
        
        # Add to uploaded_urls list
        user_data["uploaded_urls"].append(upload_record)
        
        # Save updated user data
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Error saving uploaded URL: {e}")


def get_uploaded_urls(uid):
    """Get uploaded URLs for a user."""
    try:
        user_file = _user_file(uid)
        
        if user_file.exists():
            with open(user_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
            
            return user_data.get("uploaded_urls", [])
        else:
            return []
            
    except Exception as e:
        print(f"Error getting uploaded URLs: {e}")
        return []

# Global cache for AI judgment results
_AI_JUDGMENT_CACHE = {}

# Cache file path
AI_CACHE_FILE = DATA_DIR / "ai_judgment_cache.json"

def _load_ai_cache():
    """Load AI judgment cache from file."""
    global _AI_JUDGMENT_CACHE
    try:
        if AI_CACHE_FILE.exists():
            with open(AI_CACHE_FILE, 'r', encoding='utf-8') as f:
                _AI_JUDGMENT_CACHE = json.load(f)
        else:
            _AI_JUDGMENT_CACHE = {}
    except Exception as e:
        print(f"Error loading AI cache: {e}")
        _AI_JUDGMENT_CACHE = {}

def _save_ai_cache():
    """Save AI judgment cache to file."""
    try:
        # Ensure directory exists
        AI_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(AI_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_AI_JUDGMENT_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving AI cache: {e}")

# Load cache on startup
_load_ai_cache()

def check_paper_ai_relevance(text_content, url=None):
    """Check if paper content is AI-related using LLM with caching."""
    global _AI_JUDGMENT_CACHE
    
    # Create cache key from URL or content hash
    if url:
        cache_key = url
    else:
        # Use content hash as cache key if no URL
        import hashlib
        cache_key = hashlib.md5(text_content[:1000].encode()).hexdigest()
    
    # Check cache first
    if cache_key in _AI_JUDGMENT_CACHE:
        cached_result = _AI_JUDGMENT_CACHE[cache_key]
        return cached_result['is_ai'], cached_result['confidence'], cached_result.get('tags', [])
    
    try:
        # Import paper_summarizer module
        import paper_summarizer as ps
        
        # Get the first 1000 tokens (approximate)
        first_1000 = text_content[:1000]
        
        # Read prompt from the prompts/ai_check.md file
        from langchain_core.prompts import PromptTemplate
        
        prompt_template = PromptTemplate.from_file(
            os.path.join("prompts", "ai_check.md"), 
            encoding="utf-8"
        )
        
        prompt_content = prompt_template.format(first_1000=first_1000)

        # Use the same LLM client as in paper_summarizer
        from langchain_core.messages import HumanMessage
        
        # Get LLM configuration
        api_key = llm_config.api_key
        base_url = llm_config.base_url
        provider = llm_config.provider
        model = llm_config.model
        
        # Use the same LLM invocation method
        response = ps.llm_invoke(
            [HumanMessage(content=prompt_content)],
            api_key=api_key,
            base_url=base_url,
            provider=provider,
            model=model
        )
        
        # Parse response
        response_text = response.content.strip()
        
        # Try to extract JSON from response
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        
        # Parse JSON
        print(f"Response text: {response_text}")
        result = json.loads(response_text)
        is_ai = result.get('is_ai', False)
        confidence = result.get('confidence', 0.0)
        tags = result.get('tags', [])
        
        # Cache the result
        _AI_JUDGMENT_CACHE[cache_key] = {
            'is_ai': is_ai,
            'confidence': confidence,
            'tags': tags,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save cache to file
        _save_ai_cache()
        
        return is_ai, confidence, tags
        
    except Exception as e:
        print(f"Error checking AI relevance: {e}")
        # Default to True if there's an error, to be safe
        return True, 0.5, []


def get_ai_cache_stats():
    """Get AI cache statistics for maintenance."""
    try:
        return {
            "cache_size": len(_AI_JUDGMENT_CACHE),
            "cache_file": str(AI_CACHE_FILE),
            "cache_file_exists": AI_CACHE_FILE.exists(),
            "cache_file_size": AI_CACHE_FILE.stat().st_size if AI_CACHE_FILE.exists() else 0,
            "sample_entries": list(_AI_JUDGMENT_CACHE.keys())[:5] if _AI_JUDGMENT_CACHE else []
        }
    except Exception as e:
        return {"error": str(e)}


def clear_ai_cache():
    """Clear AI cache for maintenance."""
    global _AI_JUDGMENT_CACHE
    try:
        _AI_JUDGMENT_CACHE.clear()
        _save_ai_cache()
        return {"success": True, "message": "AI cache cleared successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_ai_cache_entry(url_or_hash):
    """Get specific AI cache entry for maintenance."""
    try:
        if url_or_hash in _AI_JUDGMENT_CACHE:
            return {
                "found": True,
                "entry": _AI_JUDGMENT_CACHE[url_or_hash]
            }
        else:
            return {
                "found": False,
                "message": "Entry not found in cache"
            }
    except Exception as e:
        return {"error": str(e)}


def reload_ai_cache():
    """Reload AI cache from file for maintenance."""
    try:
        _load_ai_cache()
        return {
            "success": True, 
            "message": "AI cache reloaded successfully",
            "cache_size": len(_AI_JUDGMENT_CACHE)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.route("/uploaded_urls", methods=["GET"])
def get_uploaded_urls_route():
    """Get uploaded URLs for the current user."""
    uid = request.cookies.get("uid")
    if not uid:
        return jsonify({"error": "Login required"}), 401
    
    try:
        uploaded_urls = get_uploaded_urls(uid)
        return jsonify({
            "success": True,
            "uploaded_urls": uploaded_urls
        })
    except Exception as e:
        return jsonify({
            "error": "Failed to get uploaded URLs",
            "message": str(e)
        }), 500


@app.route("/submit_paper", methods=["POST"])
def submit_paper():
    """Handle paper URL submission from users."""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({"error": "Missing URL"}), 400
        
        paper_url = data['url'].strip()
        if not paper_url:
            return jsonify({"error": "Empty URL"}), 400
        
        # Check daily limit
        client_ip = get_client_ip()
        if not check_daily_limit(client_ip):
            return jsonify({
                "error": "Daily limit exceeded",
                "message": "您今天已经提交了3篇论文，请明天再试。"
            }), 429
        
        # Check if user is logged in
        uid = request.cookies.get("uid")
        if not uid:
            return jsonify({
                "error": "Login required",
                "message": "请先登录后再提交论文。"
            }), 401
        
        # Import paper_summarizer module
        import paper_summarizer as ps
        
        # Step 1: Resolve PDF URL
        try:
            pdf_url = ps.resolve_pdf_url(paper_url)
        except Exception as e:
            # Save failed upload attempt
            save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                "success": False,
                "error": f"PDF resolution failed: {str(e)}"
            })
            
            return jsonify({
                "error": "PDF resolution failed",
                "message": f"无法解析PDF链接: {str(e)}"
            }), 400
        
        # Step 2: Download PDF
        try:
            pdf_path = ps.download_pdf(pdf_url)
        except Exception as e:
            # Save failed upload attempt
            save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                "success": False,
                "error": f"PDF download failed: {str(e)}"
            })
            
            return jsonify({
                "error": "PDF download failed",
                "message": f"PDF下载失败: {str(e)}"
            }), 400
        
        # Step 3: Extract text
        try:
            md_path = ps.extract_markdown(pdf_path)
            text_content = md_path.read_text(encoding="utf-8")
        except Exception as e:
            # Save failed upload attempt
            save_uploaded_url(uid, paper_url, (False, 0.0, []), {
                "success": False,
                "error": f"Text extraction failed: {str(e)}"
            })
            
            return jsonify({
                "error": "Text extraction failed",
                "message": f"文本提取失败: {str(e)}"
            }), 400
        
        # Step 4: Check if paper is AI-related (with caching)
        is_ai, confidence, tags = check_paper_ai_relevance(text_content, paper_url)
        
        # Increment daily limit for any valid PDF upload (regardless of AI content)
        increment_daily_limit(client_ip)
        
        if not is_ai:
            # Save failed upload attempt
            save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                "success": False,
                "error": "Not AI paper"
            })

            print(f"Not AI paper: {paper_url}, confidence: {confidence}, tags: {tags}")
            
            return jsonify({
                "error": "Not AI paper",
                "message": "抱歉，我们只接受AI相关的论文。根据分析，这篇论文不属于AI领域。",
                "confidence": confidence
            }), 400
        
        # Step 5: Process the paper using existing pipeline
        try:
            # Use the same summarization logic as in feed_paper_summarizer_service
            import feed_paper_summarizer_service as fps
            
            # Process the paper
            summary_path, _, paper_subject = fps._summarize_url(
                paper_url,
                api_key=llm_config.api_key,
                base_url=llm_config.base_url,
                provider=llm_config.provider,
                model=llm_config.model,
                max_input_char=100000,
                extract_only=False,
                local=False,
                max_workers=paper_config.max_workers
            )
            
            if summary_path:
                # Extract arXiv ID from the summary path
                arxiv_id = summary_path.stem
                
                # Read the generated summary content
                summary_content = summary_path.read_text(encoding="utf-8")
                
                # Read the generated tags
                tags_path = SUMMARY_DIR / f"{arxiv_id}.tags.json"
                tags = {"top": [], "tags": []}
                if tags_path.exists():
                    try:
                        tags = json.loads(tags_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                
                # Create AI judgment data
                ai_judgment = {
                    "is_ai": is_ai,
                    "confidence": confidence,
                    "tags": tags
                }
                
                # Save with service record
                save_summary_with_service_record(
                    arxiv_id=arxiv_id,
                    summary_content=summary_content,
                    tags=tags,
                    source_type="user",
                    user_id=uid,
                    original_url=paper_url,
                    ai_judgment=ai_judgment
                )
                
                # Save successful upload record
                save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                    "success": True,
                    "summary_path": str(summary_path),
                    "paper_subject": paper_subject
                })
                
                # Clear cache to force refresh
                global _ENTRIES_CACHE
                _ENTRIES_CACHE = {
                    "meta": None,
                    "count": 0,
                    "latest_mtime": 0.0,
                }
                
                return jsonify({
                    "success": True,
                    "message": "论文提交成功！",
                    "summary_path": str(summary_path),
                    "paper_subject": paper_subject
                })
            else:
                # Save failed upload attempt
                save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                    "success": False,
                    "error": "Summary generation failed"
                })
                
                return jsonify({
                    "error": "Summary generation failed",
                    "message": "论文处理失败，请稍后重试。"
                }), 500
                
        except Exception as e:
            # Save failed upload attempt
            save_uploaded_url(uid, paper_url, (is_ai, confidence, tags), {
                "success": False,
                "error": f"Processing failed: {str(e)}"
            })
            
            return jsonify({
                "error": "Processing failed",
                "message": f"论文处理失败: {str(e)}"
            }), 500
            
    except Exception as e:
        return jsonify({
            "error": "Server error",
            "message": f"服务器错误: {str(e)}"
        }), 500

# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"✅ Serving summaries from {SUMMARY_DIR.resolve()}")
    print(f"📋 Configuration loaded:")
    print(f"   - LLM Provider: {llm_config.provider}")
    print(f"   - Base URL: {llm_config.base_url}")
    print(f"   - Model: {llm_config.model}")
    print(f"   - Daily Limit: {paper_config.daily_submission_limit}")
    print(f"   - Max Workers: {paper_config.max_workers}")
    app.run(
        host=app_config.host, 
        port=app_config.port, 
        debug=app_config.debug
    )