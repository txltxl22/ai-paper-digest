"""
Index page services for entry scanning, filtering, and rendering.
"""
from datetime import datetime
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import markdown
from .models import EntryMetadata, TagCloud, Pagination


class EntryScanner:
    """Service for scanning and caching entry metadata."""
    
    def __init__(self, summary_dir: Path):
        self.summary_dir = summary_dir
        self._cache: Dict = {
            "meta": None,
            "count": 0,
            "latest_mtime": 0.0,
        }
    
    def scan_entries_meta(self) -> List[Dict[str, Any]]:
        """Scan summary directory and build metadata for all entries.
        
        Returns a list of dicts with keys: id, updated, tags, top_tags, detail_tags, source_type, user_id.
        This function also maintains a lightweight cache to avoid re-reading files
        on every request when nothing changed.
        """
        # Get all .json files (new format) and .md files (legacy format)
        json_files = list(self.summary_dir.glob("*.json"))
        md_files = list(self.summary_dir.glob("*.md"))
        
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
            self._cache.get("meta") is not None
            and self._cache.get("count") == count
            and float(self._cache.get("latest_mtime") or 0.0) >= float(latest_mtime)
        ):
            return list(self._cache["meta"])

        entries_meta: List[Dict] = []
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
                tags: List[str] = []
                top_tags: List[str] = []
                detail_tags: List[str] = []
                
                tags_dict = summary_data.get("tags", {})
                if isinstance(tags_dict, dict):
                    # Handle nested structure: {"tags": {"top": [...], "tags": [...]}}
                    container = tags_dict
                    if isinstance(tags_dict.get("tags"), dict):
                        container = tags_dict.get("tags") or {}
                    
                    if isinstance(container.get("top"), list):
                        top_tags = [str(t).strip().lower() for t in container.get("top") if str(t).strip()]
                    if isinstance(container.get("tags"), list):
                        detail_tags = [str(t).strip().lower() for t in container.get("tags") if str(t).strip()]
                tags = (top_tags or []) + (detail_tags or [])
                
                # Extract English title from structured content
                english_title = None
                structured_content = summary_data.get("structured_content", {})
                if isinstance(structured_content, dict) and "paper_info" in structured_content:
                    paper_info = structured_content.get("paper_info", {})
                    if isinstance(paper_info, dict):
                        english_title = paper_info.get("title_en")
                
                # Parse updated time
                updated_str = summary_data.get("updated_at")
                if updated_str:
                    try:
                        updated = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                    except Exception:
                        updated = datetime.fromtimestamp(json_path.stat().st_mtime)
                else:
                    updated = datetime.fromtimestamp(json_path.stat().st_mtime)
                
                # Parse submission/creation time
                submission_time = updated  # Default to updated time
                created_str = service_data.get("created_at")
                if created_str:
                    try:
                        submission_time = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    except Exception:
                        submission_time = updated
                
                # Parse first creation time (original processing time)
                first_created_time = submission_time  # Default to submission time
                first_created_str = service_data.get("first_created_at")
                if first_created_str:
                    try:
                        first_created_time = datetime.fromisoformat(first_created_str.replace('Z', '+00:00'))
                    except Exception:
                        first_created_time = submission_time
                
                entries_meta.append({
                    "id": arxiv_id,
                    "updated": updated,
                    "submission_time": submission_time,
                    "first_created_time": first_created_time,
                    "tags": tags,
                    "top_tags": top_tags,
                    "detail_tags": detail_tags,
                    "source_type": service_data.get("source_type", "system"),
                    "user_id": service_data.get("user_id"),
                    "original_url": service_data.get("original_url"),
                    "abstract": service_data.get("abstract"),
                    "english_title": english_title,
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
                submission_time = updated  # For legacy files, use file mtime as submission time
                first_created_time = updated  # For legacy files, use file mtime as first creation time

                # Load tags from legacy .tags.json file
                tags: List[str] = []
                top_tags: List[str] = []
                detail_tags: List[str] = []
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
                    "submission_time": submission_time,
                    "first_created_time": first_created_time,
                    "tags": tags,
                    "top_tags": top_tags,
                    "detail_tags": detail_tags,
                    "source_type": "system",  # Legacy files default to system
                    "user_id": None,
                    "original_url": None,
                    "abstract": None,  # Legacy files don't have abstract
                    "english_title": None,  # Legacy files don't have structured titles
                })
                processed_ids.add(arxiv_id)
            except Exception as e:
                print(f"Error processing legacy MD file {md_path}: {e}")
                continue

        # Sort by updated time (newest first), then by submission time as secondary sort
        entries_meta.sort(key=lambda e: (e["updated"], e["submission_time"]), reverse=True)
        self._cache["meta"] = list(entries_meta)
        self._cache["count"] = count
        self._cache["latest_mtime"] = latest_mtime
        return entries_meta
    
    def clear_cache(self):
        """Clear the internal cache to force re-scanning on next request."""
        self._cache = {
            "meta": None,
            "count": 0,
            "latest_mtime": 0.0,
        }


class EntryRenderer:
    """Service for rendering entry previews."""
    
    def __init__(self, summary_dir: Path):
        self.summary_dir = summary_dir
    
    def render_markdown(self, md_text: str) -> str:
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
    
    def render_page_entries(self, entries_meta: List[Dict], user_data=None, show_read_time=False, show_favorite_time=False) -> List[Dict]:
        """Given a slice of entries meta, materialize preview_html for each."""
        rendered: List[Dict] = []
        
        # Get favorites map and read map if user data is provided
        favorites_map = {}
        read_map = {}
        if user_data:
            favorites_map = user_data.load_favorites_map()
            read_map = user_data.load_read_map()
        
        for meta in entries_meta:
            try:
                # Try to load from new JSON format first
                json_path = self.summary_dir / f"{meta['id']}.json"
                if json_path.exists():
                    data = json.loads(json_path.read_text(encoding="utf-8"))
                    summary_data = data.get("summary_data", {})
                    md_text = summary_data.get("markdown_content", summary_data.get("content", ""))
                    
                    # If markdown content is empty or None, try to generate from structured content
                    if not md_text and "structured_content" in summary_data:
                        try:
                            structured_content = summary_data.get("structured_content", {})
                            if structured_content and isinstance(structured_content, dict):
                                if "paper_info" in structured_content:
                                    # Use the structured content directly - it should already be in the right format
                                    from summary_service.models import parse_summary
                                    structured_summary = parse_summary(json.dumps(structured_content))
                                    md_text = structured_summary.to_markdown()
                                elif "content" in structured_content:
                                    # This should not happen anymore with the fix above
                                    logging.warning(f"Found legacy content in structured_content for {meta['id']}")
                                    md_text = structured_content.get("content", "")
                        except Exception as e:
                            logging.error(f"Error converting structured content to markdown: {e}")
                    
                    # If content is still empty, try to fall back to .md file
                    if not md_text:
                        md_path = self.summary_dir / f"{meta['id']}.md"
                        if md_path.exists():
                            md_text = md_path.read_text(encoding="utf-8", errors="ignore")
                        else:
                            # No content available, show a message
                            md_text = f"## 📄 论文总结\n\n**{meta['id']}**\n\n⚠️ 内容暂时不可用\n\n该论文的摘要内容当前不可用。请稍后再试或联系管理员。"
                else:
                    # Fallback to legacy .md file
                    md_path = self.summary_dir / f"{meta['id']}.md"
                    md_text = md_path.read_text(encoding="utf-8", errors="ignore")
                
                preview_html = self.render_markdown(md_text)
            except Exception:
                preview_html = ""
            item = dict(meta)
            item["preview_html"] = preview_html
            item["is_favorited"] = meta["id"] in favorites_map
            
            # Add timestamp information if requested
            if show_read_time and meta["id"] in read_map:
                item["read_time"] = read_map[meta["id"]]
            if show_favorite_time and meta["id"] in favorites_map:
                item["favorite_time"] = favorites_map[meta["id"]]
                
            rendered.append(item)
        return rendered


class EntryFilter:
    """Service for filtering entries based on various criteria."""
    
    @staticmethod
    def filter_by_read_status(entries: List[Dict], read_ids: set, show_read: bool = False) -> List[Dict]:
        """Filter entries by read status."""
        if show_read:
            return [e for e in entries if e["id"] in read_ids]
        else:
            return [e for e in entries if e["id"] not in read_ids]
    
    @staticmethod
    def filter_by_tag(entries: List[Dict], active_tag: str) -> List[Dict]:
        """Filter entries by active tag."""
        if not active_tag:
            return entries
        return [e for e in entries if active_tag in (e.get("detail_tags") or []) or active_tag in (e.get("top_tags") or [])]
    
    @staticmethod
    def filter_by_tag_query(entries: List[Dict], tag_query: str) -> List[Dict]:
        """Filter entries by tag query (partial match)."""
        if not tag_query:
            return entries
        
        def matches_query(tags: List[str] | None, query: str) -> bool:
            if not tags:
                return False
            for t in tags:
                if query in t:
                    return True
            return False
        
        return [e for e in entries if matches_query(e.get("detail_tags"), tag_query) or matches_query(e.get("top_tags"), tag_query)]
    
    @staticmethod
    def filter_by_top_tags(entries: List[Dict], active_tops: List[str]) -> List[Dict]:
        """Filter entries by top tags."""
        if not active_tops:
            return entries
        return [e for e in entries if any(t in (e.get("top_tags") or []) for t in active_tops)]
