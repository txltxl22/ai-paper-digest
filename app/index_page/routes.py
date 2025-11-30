"""
Index page routes for main index and read pages.
"""
from flask import Blueprint, request, render_template_string, make_response, redirect, url_for
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
from .services import EntryScanner, EntryRenderer, EntryFilter
from .models import TagCloud, Pagination
from summary_service.recommendations import RecommendationContext, RecommendationEngine, RecommendationResponse


def create_index_routes(
    entry_scanner: EntryScanner,
    entry_renderer: EntryRenderer,
    user_service,
    index_template: str,
    detail_template: str,
    paper_config=None,
    search_service=None,
    recommendation_engine: RecommendationEngine | None = None,
) -> Blueprint:
    """Create index page routes."""
    bp = Blueprint('index_page', __name__)
    
    def _get_filter_params() -> Dict[str, Any]:
        """Extract and validate filter parameters from request."""
        search_type = request.args.get("search_type", "all").strip()
        if search_type not in ["all", "content", "tags"]:
            search_type = "all"
            
        return {
            'active_tag': (request.args.get("tag") or "").strip().lower() or None,
            'tag_query': (request.args.get("q") or "").strip().lower(),
            'search_query': (request.args.get("search") or "").strip(),
            'search_type': search_type,
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
        
        # Apply search filter if search service is available
        if filters['search_query'] and search_service:
            # Determine search fields based on search type
            search_fields = []
            if filters['search_type'] == 'all':
                search_fields = ['title', 'content', 'tags']
            elif filters['search_type'] == 'content':
                search_fields = ['title', 'content']
            elif filters['search_type'] == 'tags':
                search_fields = ['tags']
            
            if search_fields:
                search_results = search_service.search(filters['search_query'], search_fields)
                search_ids = {result['id'] for result in search_results}
                entries = [e for e in entries if e['id'] in search_ids]
        
        return entries
    
    def _build_template_context(
        entries: List[Dict],
        uid: Optional[str],
        filters: Dict[str, Any],
        pagination: Pagination,
        show_read: bool = False,
        show_favorites: bool = False,
        show_todo: bool = False,
        user_stats: Optional[Dict] = None,
        all_entries: Optional[List[Dict]] = None,
        personalization: Optional[Dict[str, Any]] = None,
        papers_updated_24h: int = 0,
        papers_updated_72h: int = 0,
        latest_paper: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the template context with all necessary data."""
        # Build tag clouds from all entries (not just filtered ones)
        tag_cloud = TagCloud()
        top_cloud = TagCloud()
        entries_for_cloud = all_entries if all_entries is not None else entries
        for e in entries_for_cloud:
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
            'search_query': filters['search_query'],
            'search_type': filters['search_type'],
            'admin_users': admin_users,
            'show_read': show_read,
            'show_favorites': show_favorites,
            'show_todo': show_todo,
            # Paper submission config
            'daily_submission_limit': paper_config.daily_submission_limit if paper_config else 3,
            'max_pdf_size_mb': paper_config.max_pdf_size_mb if paper_config else 20,
            # Admin URLs
            'admin_fetch_url': url_for("fetch.admin_fetch_latest"),
            'admin_stream_url': url_for("fetch.admin_fetch_latest_stream"),
            # User management URLs
            'mark_read_url': url_for("user_management.mark_read", arxiv_id="__ID__").replace("__ID__", ""),
            'unmark_read_url': url_for("user_management.unmark_read", arxiv_id="__ID__").replace("__ID__", ""),
            'mark_favorite_url': url_for("user_management.mark_favorite", arxiv_id="__ID__").replace("__ID__", ""),
            'unmark_favorite_url': url_for("user_management.unmark_favorite", arxiv_id="__ID__").replace("__ID__", ""),
            'mark_todo_url': url_for("user_management.mark_todo", arxiv_id="__ID__").replace("__ID__", ""),
            'unmark_todo_url': url_for("user_management.unmark_todo", arxiv_id="__ID__").replace("__ID__", ""),
            'reset_url': url_for("user_management.reset_read"),
            'personalization': personalization or {'active': False},
            **pagination.to_dict()
        }
        
        # Add user-specific data
        if user_stats:
            context.update({
                'unread_count': user_stats.get('unread_count'),
                'read_total': user_stats.get('read_total'),
                'read_today': user_stats.get('read_today'),
                'todo_count': user_stats.get('todo_count')
            })
        else:
            context.update({
                'unread_count': None,
                'read_total': None,
                'read_today': None,
                'todo_count': None
            })
        
        # Add update statistics
        context.update({
            'papers_updated_24h': papers_updated_24h,
            'papers_updated_72h': papers_updated_72h,
            'latest_paper': latest_paper,
        })
        
        return context
    
    def _apply_recommendations(
        entries: List[Dict[str, Any]],
        favorites_meta: List[Dict[str, Any]],
        favorites_map: Dict[str, Optional[str]],
        read_meta: List[Dict[str, Any]],
        read_map: Dict[str, Optional[str]],
        uid: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if (
            not recommendation_engine
            or not favorites_meta
            or not favorites_map
            or not entries
        ):
            return entries, {'active': False}

        context = RecommendationContext(
            candidate_entries=entries,
            favorites_meta=favorites_meta,
            favorites_map=favorites_map,
            read_meta=read_meta,
            read_map=read_map,
            extra={'uid': uid} if uid else {},
        )
        response: RecommendationResponse = recommendation_engine.recommend(context)
        if not response.scores:
            # User has favorites but no recommendations were generated
            tag_profile = response.profiles.get("tag_preference") if response.profiles else {}
            return entries, {
                'active': False,
                'has_favorites': True,  # Flag to indicate user has favorites but no matches
                'profiles': response.profiles,
                'top_tags': (tag_profile or {}).get("top_tags", []),
                'generated_at': response.generated_at.isoformat(),
            }

        annotated: List[Dict[str, Any]] = []
        for entry in entries:
            entry_copy = dict(entry)
            rec_score = response.scores.get(entry_copy.get("id"))
            if rec_score:
                entry_copy["recommendation"] = {
                    "score": rec_score.score,
                    "matched_tags": rec_score.matched_tags,
                    "breakdown": rec_score.breakdown,
                    "metadata": rec_score.metadata,
                }
            else:
                entry_copy["recommendation"] = None
            annotated.append(entry_copy)

        def _sort_key(item: Dict[str, Any]) -> Tuple[int, float]:
            rec = item.get("recommendation") or {}
            score = float(rec.get("score") or 0.0)
            has_reco = 0 if score > 0 else 1
            # Use submission_time (creation date) for ordering within each group
            submission = item.get("submission_time")
            if submission and hasattr(submission, "timestamp"):
                submission_ts = submission.timestamp()
            else:
                # Fallback to updated time if submission_time not available
                updated = item.get("updated")
                submission_ts = updated.timestamp() if hasattr(updated, "timestamp") else 0.0
            # Sort by: 1) has recommendation (0=yes, 1=no), 2) creation time (newest first)
            return (has_reco, -submission_ts)

        annotated.sort(key=_sort_key)

        tag_profile = response.profiles.get("tag_preference") if response.profiles else {}
        personalization = {
            'active': True,
            'matched_entries': len(response.scores),
            'top_tags': (tag_profile or {}).get("top_tags", []),
            'generated_at': response.generated_at.isoformat(),
        }
        return annotated, personalization

    @bp.route("/", methods=["GET"])
    def index():
        """Main index page."""
        uid = user_service.get_current_user_id()
        all_entries_meta = entry_scanner.scan_entries_meta()
        filters = _get_filter_params()
        pagination_params = _get_pagination_params()
        
        # Calculate update statistics
        now = datetime.now(timezone.utc)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_72h = now - timedelta(hours=72)
        
        def normalize_datetime(dt):
            """Normalize datetime to UTC for comparison."""
            if dt is None:
                return None
            if dt.tzinfo is None:
                # Assume naive datetime is in UTC
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        
        papers_updated_24h = len([
            e for e in all_entries_meta 
            if e.get("updated") and (normalized := normalize_datetime(e["updated"])) and normalized >= cutoff_24h
        ])
        papers_updated_72h = len([
            e for e in all_entries_meta 
            if e.get("updated") and (normalized := normalize_datetime(e["updated"])) and normalized >= cutoff_72h
        ])
        
        # Find latest paper by first_created_time
        latest_paper = None
        if all_entries_meta:
            latest_entry = max(
                all_entries_meta,
                key=lambda e: e.get("first_created_time") or datetime.min
            )
            if latest_entry.get("first_created_time"):
                latest_paper = {
                    'id': latest_entry.get("id"),
                    'title': latest_entry.get("english_title") or latest_entry.get("id"),
                    'first_created_time': latest_entry.get("first_created_time"),
                }
        
        # Get user data and stats
        user_stats = None
        personalization = {'active': False}
        favorites_map: Dict[str, Optional[str]] = {}
        user_data = user_service.get_user_data(uid) if uid else None
        if user_data:
            read_map = user_data.load_read_map()
            favorites_map = user_data.load_favorites_map()
            todo_map = user_data.load_todo_map()
            
            # For index page: filter out read papers and todo papers
            read_ids = set(read_map.keys())
            todo_ids = set(todo_map.keys())
            
            # Filter out read entries and todo entries
            entries_meta = EntryFilter.filter_by_read_status(all_entries_meta, read_ids, show_read=False)
            entries_meta = [e for e in entries_meta if e["id"] not in todo_ids]
            
            # Calculate stats - separate read, favorite, and todo counts
            unread_count = len([e for e in all_entries_meta if e["id"] not in read_ids])
            todo_count = len(todo_ids)
            stats = user_data.get_read_stats()
            
            user_stats = {
                'unread_count': unread_count,
                'read_total': stats["read_total"],
                'read_today': stats["read_today"],
                'todo_count': todo_count
            }
        else:
            entries_meta = all_entries_meta
            favorites_map = {}
        
        # Apply filters
        filtered_entries_meta = _apply_filters(entries_meta, filters)

        if favorites_map:
            favorites_meta = [e for e in all_entries_meta if e["id"] in favorites_map]
            if favorites_meta:
                # Build read_meta for negative signals
                read_meta: List[Dict[str, Any]] = []
                read_map: Dict[str, Optional[str]] = {}
                if user_data:
                    read_map = user_data.load_read_map()
                    read_meta = [e for e in all_entries_meta if e["id"] in read_map]
                
                filtered_entries_meta, personalization = _apply_recommendations(
                    filtered_entries_meta,
                    favorites_meta,
                    favorites_map,
                    read_meta,
                    read_map,
                    uid,
                )
            else:
                # User has favorites but they don't exist in summary directory
                personalization = {
                    'active': False,
                    'has_favorites': True,
                    'no_favorites_in_summary': True,  # Flag for missing favorite papers
                }
        elif not uid:
            # Show promotional banner for non-logged-in users
            personalization = {
                'active': False,
                'promotional': True,
            }
        
        # Pagination
        pagination = Pagination(len(filtered_entries_meta), pagination_params['page'], pagination_params['per_page'])
        page_entries = pagination.get_page_items(filtered_entries_meta)
        
        # Render entries
        entries = entry_renderer.render_page_entries(page_entries, user_data)
        
        # Build context and render - use all_entries_meta for tag cloud, filtered_entries_meta for display
        context = _build_template_context(
            entries,
            uid,
            filters,
            pagination,
            user_stats=user_stats,
            all_entries=all_entries_meta,
            personalization=personalization,
            papers_updated_24h=papers_updated_24h,
            papers_updated_72h=papers_updated_72h,
            latest_paper=latest_paper,
        )
        return make_response(render_template_string(index_template, **context))
    
    @bp.route("/read")
    def read_papers():
        """Read papers page."""
        uid = user_service.require_auth()
        if not isinstance(uid, str):
            return uid  # This will be a redirect response
        
        # Get read entries (include both explicitly read and favorited papers)
        user_data = user_service.get_user_data(uid)
        read_map = user_data.load_read_map()
        favorites_map = user_data.load_favorites_map()
        
        # Combine read and favorite IDs (favorites are considered read)
        read_ids = set(read_map.keys())
        favorite_ids = set(favorites_map.keys())
        all_read_ids = read_ids.union(favorite_ids)
        
        all_entries_meta = entry_scanner.scan_entries_meta()
        read_entries_meta = [e for e in all_entries_meta if e["id"] in all_read_ids]
        
        # Apply filters
        filters = _get_filter_params()
        filtered_read_entries_meta = _apply_filters(read_entries_meta, filters)
        
        # Pagination (allow more items per page for read list)
        pagination_params = _get_pagination_params()
        pagination_params['per_page'] = max(1, min(pagination_params['per_page'], 100))
        pagination = Pagination(len(filtered_read_entries_meta), pagination_params['page'], pagination_params['per_page'])
        page_entries = pagination.get_page_items(filtered_read_entries_meta)
        
        # Render entries (show both read and favorite timestamps in read list)
        user_data = user_service.get_user_data(uid)
        entries = entry_renderer.render_page_entries(page_entries, user_data, show_read_time=True, show_favorite_time=True)
        
        # Build context and render - use all_entries_meta for tag cloud
        context = _build_template_context(entries, uid, filters, pagination, show_read=True, all_entries=all_entries_meta)
        return render_template_string(index_template, **context)
    
    @bp.route("/favorites")
    def favorite_papers():
        """Favorite papers page."""
        uid = user_service.require_auth()
        if not isinstance(uid, str):
            return uid  # This will be a redirect response
        
        # Get favorite entries
        user_data = user_service.get_user_data(uid)
        favorites_map = user_data.load_favorites_map()
        all_entries_meta = entry_scanner.scan_entries_meta()
        favorite_entries_meta = [e for e in all_entries_meta if e["id"] in set(favorites_map.keys())]
        
        # Apply filters
        filters = _get_filter_params()
        filtered_favorite_entries_meta = _apply_filters(favorite_entries_meta, filters)
        
        # Pagination (allow more items per page for favorites list)
        pagination_params = _get_pagination_params()
        pagination_params['per_page'] = max(1, min(pagination_params['per_page'], 100))
        pagination = Pagination(len(filtered_favorite_entries_meta), pagination_params['page'], pagination_params['per_page'])
        page_entries = pagination.get_page_items(filtered_favorite_entries_meta)
        
        # Render entries
        user_data = user_service.get_user_data(uid)
        entries = entry_renderer.render_page_entries(page_entries, user_data, show_favorite_time=True)
        
        # Build context and render - use all_entries_meta for tag cloud
        context = _build_template_context(entries, uid, filters, pagination, show_favorites=True, all_entries=all_entries_meta)
        return render_template_string(index_template, **context)
    
    @bp.route("/todo")
    def todo_papers():
        """Todo papers page."""
        uid = user_service.require_auth()
        if not isinstance(uid, str):
            return uid  # This will be a redirect response
        
        # Get todo entries
        user_data = user_service.get_user_data(uid)
        todo_map = user_data.load_todo_map()
        all_entries_meta = entry_scanner.scan_entries_meta()
        todo_entries_meta = [e for e in all_entries_meta if e["id"] in set(todo_map.keys())]
        
        # Apply filters
        filters = _get_filter_params()
        filtered_todo_entries_meta = _apply_filters(todo_entries_meta, filters)
        
        # Pagination (allow more items per page for todo list)
        pagination_params = _get_pagination_params()
        pagination_params['per_page'] = max(1, min(pagination_params['per_page'], 100))
        pagination = Pagination(len(filtered_todo_entries_meta), pagination_params['page'], pagination_params['per_page'])
        page_entries = pagination.get_page_items(filtered_todo_entries_meta)
        
        # Render entries
        user_data = user_service.get_user_data(uid)
        entries = entry_renderer.render_page_entries(page_entries, user_data, show_todo_time=True)
        
        # Build context and render - use all_entries_meta for tag cloud
        context = _build_template_context(entries, uid, filters, pagination, show_todo=True, all_entries=all_entries_meta)
        return render_template_string(index_template, **context)
    
    return bp
