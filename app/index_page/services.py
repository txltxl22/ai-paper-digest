"""
Index page services for entry scanning, filtering, and rendering.
"""
from datetime import datetime
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
        self._cache["meta"] = list(entries_meta)
        self._cache["count"] = count
        self._cache["latest_mtime"] = latest_mtime
        return entries_meta


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
    
    def render_page_entries(self, entries_meta: List[Dict]) -> List[Dict]:
        """Given a slice of entries meta, materialize preview_html for each."""
        rendered: List[Dict] = []
        for meta in entries_meta:
            try:
                # Try to load from new JSON format first
                json_path = self.summary_dir / f"{meta['id']}.json"
                if json_path.exists():
                    data = json.loads(json_path.read_text(encoding="utf-8"))
                    summary_data = data.get("summary_data", {})
                    md_text = summary_data.get("content", "")
                else:
                    # Fallback to legacy .md file
                    md_path = self.summary_dir / f"{meta['id']}.md"
                    md_text = md_path.read_text(encoding="utf-8", errors="ignore")
                
                preview_html = self.render_markdown(md_text)
            except Exception:
                preview_html = ""
            item = dict(meta)
            item["preview_html"] = preview_html
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
