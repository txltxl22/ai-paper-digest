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
        
        # Process new JSON format files first using Pydantic models
        from summary_service.record_manager import load_summary_with_service_record
        for json_path in json_files:
            try:
                arxiv_id = json_path.stem
                if arxiv_id in processed_ids:
                    continue
                
                # Load using Pydantic model
                record = load_summary_with_service_record(arxiv_id, self.summary_dir)
                if not record:
                    continue
                
                # Skip summaries without one_sentence_summary (not fully processed)
                one_sentence_summary = record.summary_data.structured_content.one_sentence_summary
                if not one_sentence_summary or not one_sentence_summary.strip():
                    continue
                
                # Extract tags from Tags model
                tags_obj = record.summary_data.tags
                top_tags = [str(t).strip().lower() for t in (tags_obj.top or []) if str(t).strip()]
                detail_tags = [str(t).strip().lower() for t in (tags_obj.tags or []) if str(t).strip()]
                tags = top_tags + detail_tags
                
                # Extract English title and abstract from PaperInfo
                paper_info = record.summary_data.structured_content.paper_info
                english_title = paper_info.title_en
                abstract = paper_info.abstract
                
                # Parse updated time
                updated_str = record.summary_data.updated_at
                if updated_str:
                    try:
                        updated = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                    except Exception:
                        updated = datetime.fromtimestamp(json_path.stat().st_mtime)
                else:
                    updated = datetime.fromtimestamp(json_path.stat().st_mtime)
                
                # Parse submission time - use arXiv submission date only
                submission_time = None
                if paper_info.submission_date:
                    try:
                        # Parse ISO date format (YYYY-MM-DD) to datetime
                        submission_time = datetime.strptime(paper_info.submission_date, '%Y-%m-%d')
                    except Exception:
                        pass  # Keep as None if parsing fails
                
                # Parse first creation time (original processing time)
                first_created_time = updated  # Default to updated time
                first_created_str = record.service_data.first_created_at
                if first_created_str:
                    try:
                        first_created_time = datetime.fromisoformat(first_created_str.replace('Z', '+00:00'))
                    except Exception:
                        first_created_time = updated
                
                entries_meta.append({
                    "id": arxiv_id,
                    "updated": updated,
                    "submission_time": submission_time,
                    "first_created_time": first_created_time,
                    "tags": tags,
                    "top_tags": top_tags,
                    "detail_tags": detail_tags,
                    "source_type": record.service_data.source_type or "system",
                    "user_id": record.service_data.user_id,
                    "original_url": record.service_data.original_url,
                    "abstract": abstract,  # From PaperInfo in structured_content
                    "english_title": english_title,
                    "is_abstract_only": bool(record.service_data.is_abstract_only or False),
                })
                processed_ids.add(arxiv_id)
            except Exception as e:
                print(f"Error processing JSON file {json_path}: {e}")
                continue
        
        # Sort by submission time (arXiv date) if available, otherwise by updated time
        # None submission_time entries are sorted to the end
        entries_meta.sort(
            key=lambda e: (e["submission_time"] or datetime.min, e["updated"]),
            reverse=True
        )
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
    
    def render_page_entries(self, entries_meta: List[Dict], user_data=None, show_read_time=False, show_favorite_time=False, show_todo_time=False) -> List[Dict]:
        """Given a slice of entries meta, materialize preview_html for each."""
        rendered: List[Dict] = []
        
        # Get favorites map, read map, and todo map if user data is provided
        favorites_map = {}
        read_map = {}
        todo_map = {}
        if user_data:
            favorites_map = user_data.load_favorites_map()
            read_map = user_data.load_read_map()
            todo_map = user_data.load_todo_map()
        
        for meta in entries_meta:
            try:
                # Try to load from new JSON format first using Pydantic models
                json_path = self.summary_dir / f"{meta['id']}.json"
                if json_path.exists():
                    try:
                        from summary_service.record_manager import load_summary_with_service_record
                        record = load_summary_with_service_record(meta['id'], self.summary_dir)
                        if record:
                            # markdown_content is guaranteed to be populated by load_summary_with_service_record
                            md_text = record.summary_data.markdown_content
                        else:
                            md_text = None
                    except Exception as e:
                        logging.error(f"Error loading record for {meta['id']}: {e}")
                        md_text = None
                    
                    # If content is still empty, try to fall back to .md file
                    if not md_text:
                        md_path = self.summary_dir / f"{meta['id']}.md"
                        if md_path.exists():
                            md_text = md_path.read_text(encoding="utf-8", errors="ignore")
                        else:
                            # No content available, show a message
                            md_text = f"**{meta['id']}**\n\n⚠️ 内容暂时不可用\n\n该论文的摘要内容当前不可用。请稍后再试或联系管理员。"
                else:
                    # Fallback to legacy .md file
                    md_path = self.summary_dir / f"{meta['id']}.md"
                    md_text = md_path.read_text(encoding="utf-8", errors="ignore")
                
                # Truncate md_text to ensure only the visible summary part is in the preview
                # For new format (has <div class="deep-section"), we strip that and everything after
                if '<div class="deep-section"' in md_text:
                    md_text = md_text.split('<div class="deep-section"', 1)[0]
                # For legacy format, try to split at "### 2️⃣" or similar known headers
                elif "### 2️⃣" in md_text:
                    md_text = md_text.split("### 2️⃣", 1)[0]
                elif "## Innovations" in md_text:
                    md_text = md_text.split("## Innovations", 1)[0]
                elif "### Innovations" in md_text:
                    md_text = md_text.split("### Innovations", 1)[0]
                
                # Strip trailing whitespace and potential markdown horizontal rules
                md_text = md_text.strip()
                while md_text.endswith("---") or md_text.endswith("***") or md_text.endswith("___"):
                    md_text = md_text[:-3].strip()
                
                preview_html = self.render_markdown(md_text)
            except Exception:
                preview_html = ""
            item = dict(meta)
            item.setdefault("recommendation", None)
            item["preview_html"] = preview_html
            item["is_favorited"] = meta["id"] in favorites_map
            item["is_todo"] = meta["id"] in todo_map
            
            # Add timestamp information if requested
            if show_read_time and meta["id"] in read_map:
                item["read_time"] = read_map[meta["id"]]
            if show_favorite_time and meta["id"] in favorites_map:
                item["favorite_time"] = favorites_map[meta["id"]]
            if show_todo_time and meta["id"] in todo_map:
                item["todo_time"] = todo_map[meta["id"]]
                
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
