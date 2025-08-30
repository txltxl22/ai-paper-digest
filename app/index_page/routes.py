"""
Index page routes for main index and read pages.
"""
from flask import Blueprint, request, render_template_string, make_response, redirect, url_for
from typing import List, Optional, Dict, Any
from .services import EntryScanner, EntryRenderer, EntryFilter
from .models import TagCloud, Pagination


def create_index_routes(
    entry_scanner: EntryScanner,
    entry_renderer: EntryRenderer,
    user_service,
    index_template: str,
    detail_template: str
) -> Blueprint:
    """Create index page routes."""
    bp = Blueprint('index_page', __name__)
    
    def _get_filter_params() -> Dict[str, Any]:
        """Extract and validate filter parameters from request."""
        return {
            'active_tag': (request.args.get("tag") or "").strip().lower() or None,
            'tag_query': (request.args.get("q") or "").strip().lower(),
            'active_tops': [t.strip().lower() for t in request.args.getlist("top") if t.strip()]
        }
    
    def _get_pagination_params() -> Dict[str, int]:
        """Extract and validate pagination parameters from request."""
        try:
            page = max(1, int(request.args.get("page", 1)))
        except Exception:
            page = 1
        try:
            per_page = int(request.args.get("per_page", 10))
        except Exception:
            per_page = 10
        return {
            'page': page,
            'per_page': max(1, min(per_page, 30))
        }
    
    def _apply_filters(entries: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """Apply all filters to entries."""
        if filters['active_tag']:
            entries = EntryFilter.filter_by_tag(entries, filters['active_tag'])
        if filters['tag_query']:
            entries = EntryFilter.filter_by_tag_query(entries, filters['tag_query'])
        if filters['active_tops']:
            entries = EntryFilter.filter_by_top_tags(entries, filters['active_tops'])
        return entries
    
    def _build_template_context(
        entries: List[Dict],
        uid: Optional[str],
        filters: Dict[str, Any],
        pagination: Pagination,
        show_read: bool = False,
        user_stats: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Build the template context with all necessary data."""
        # Build tag clouds
        tag_cloud = TagCloud()
        top_cloud = TagCloud()
        for e in entries:
            tag_cloud.add_entry(e)
            top_cloud.add_entry(e)
        
        # Get admin users
        admin_users = [admin_id.strip() for admin_id in user_service.admin_user_ids if admin_id.strip()]
        
        context = {
            'entries': entries,
            'uid': uid,
            'tag_cloud': tag_cloud.get_tag_cloud(filters['tag_query'] if filters['tag_query'] else None),
            'top_cloud': top_cloud.get_top_cloud(),
            'active_tag': filters['active_tag'],
            'active_tops': filters['active_tops'],
            'tag_query': filters['tag_query'],
            'admin_users': admin_users,
            'show_read': show_read,
            # Admin URLs
            'admin_fetch_url': url_for("admin_fetch_latest"),
            'admin_stream_url': url_for("admin_fetch_latest_stream"),
            # User management URLs
            'mark_read_url': url_for("user_management.mark_read", arxiv_id="__ID__").replace("__ID__", ""),
            'unmark_read_url': url_for("user_management.unmark_read", arxiv_id="__ID__").replace("__ID__", ""),
            'reset_url': url_for("user_management.reset_read"),
            **pagination.to_dict()
        }
        
        # Add user-specific data
        if user_stats:
            context.update({
                'unread_count': user_stats.get('unread_count'),
                'read_total': user_stats.get('read_total'),
                'read_today': user_stats.get('read_today')
            })
        else:
            context.update({
                'unread_count': None,
                'read_total': None,
                'read_today': None
            })
        
        return context
    
    @bp.route("/", methods=["GET"])
    def index():
        """Main index page."""
        uid = user_service.get_current_user_id()
        entries_meta = entry_scanner.scan_entries_meta()
        filters = _get_filter_params()
        pagination_params = _get_pagination_params()
        
        # Get user data and stats
        user_stats = None
        if uid:
            user_data = user_service.get_user_data(uid)
            read_map = user_data.load_read_map()
            read_ids = set(read_map.keys())
            
            # Filter out read entries
            entries_meta = EntryFilter.filter_by_read_status(entries_meta, read_ids, show_read=False)
            
            # Calculate stats
            unread_count = len([e for e in entry_scanner.scan_entries_meta() if e["id"] not in read_ids])
            stats = user_data.get_read_stats()
            user_stats = {
                'unread_count': unread_count,
                'read_total': stats["read_total"],
                'read_today': stats["read_today"]
            }
        
        # Apply filters
        entries_meta = _apply_filters(entries_meta, filters)
        
        # Pagination
        pagination = Pagination(len(entries_meta), pagination_params['page'], pagination_params['per_page'])
        page_entries = pagination.get_page_items(entries_meta)
        
        # Render entries
        entries = entry_renderer.render_page_entries(page_entries)
        
        # Build context and render
        context = _build_template_context(entries, uid, filters, pagination, user_stats=user_stats)
        return make_response(render_template_string(index_template, **context))
    
    @bp.route("/read")
    def read_papers():
        """Read papers page."""
        uid = user_service.require_auth()
        if not isinstance(uid, str):
            return uid  # This will be a redirect response
        
        # Get read entries
        user_data = user_service.get_user_data(uid)
        read_map = user_data.load_read_map()
        entries_meta = entry_scanner.scan_entries_meta()
        read_entries_meta = [e for e in entries_meta if e["id"] in set(read_map.keys())]
        
        # Apply filters
        filters = _get_filter_params()
        read_entries_meta = _apply_filters(read_entries_meta, filters)
        
        # Pagination (allow more items per page for read list)
        pagination_params = _get_pagination_params()
        pagination_params['per_page'] = max(1, min(pagination_params['per_page'], 100))
        pagination = Pagination(len(read_entries_meta), pagination_params['page'], pagination_params['per_page'])
        page_entries = pagination.get_page_items(read_entries_meta)
        
        # Render entries
        entries = entry_renderer.render_page_entries(page_entries)
        
        # Build context and render
        context = _build_template_context(entries, uid, filters, pagination, show_read=True)
        return render_template_string(index_template, **context)
    
    return bp
