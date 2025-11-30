"""
Search services for paper content search functionality.
"""
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from summary_service.models import SummaryRecord


class SearchService:
    """Service for searching papers by content, title, and tags."""
    
    def __init__(self, summary_dir: Path):
        self.summary_dir = summary_dir
        self._cache: Dict = {
            "content_index": None,
            "count": 0,
            "latest_mtime": 0.0,
        }
    
    def _build_content_index(self) -> List[Dict[str, Any]]:
        """Build a searchable content index from all papers."""
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
            self._cache.get("content_index") is not None
            and self._cache.get("count") == count
            and float(self._cache.get("latest_mtime") or 0.0) >= float(latest_mtime)
        ):
            return list(self._cache["content_index"])

        content_index: List[Dict] = []
        processed_ids = set()
        
        # Process new JSON format files first using Pydantic models
        from summary_service.record_manager import load_summary_with_service_record
        for json_path in json_files:
            try:
                arxiv_id = json_path.stem
                if arxiv_id in processed_ids:
                    continue
                    
                record = load_summary_with_service_record(arxiv_id, self.summary_dir)
                if not record:
                    continue
                
                # Extract searchable content
                searchable_content = self._extract_searchable_content(record, arxiv_id)
                if searchable_content:
                    content_index.append(searchable_content)
                    processed_ids.add(arxiv_id)
            except Exception as e:
                logging.error(f"Error processing JSON file {json_path} for search index: {e}")
                continue
        
        # Process legacy .md files
        for md_path in md_files:
            try:
                arxiv_id = md_path.stem
                if arxiv_id in processed_ids:
                    continue
                    
                # Load content from markdown file
                md_content = md_path.read_text(encoding="utf-8", errors="ignore")
                
                # Load tags from legacy .tags.json file
                tags: List[str] = []
                top_tags: List[str] = []
                detail_tags: List[str] = []
                tags_file = md_path.with_suffix("")
                tags_file = tags_file.with_name(tags_file.name + ".tags.json")
                try:
                    if tags_file.exists():
                        data = json.loads(tags_file.read_text(encoding="utf-8"))
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

                # Extract title from markdown content
                title = self._extract_title_from_markdown(md_content)
                
                searchable_content = {
                    "id": arxiv_id,
                    "title": title,
                    "content": md_content,
                    "tags": tags,
                    "top_tags": top_tags,
                    "detail_tags": detail_tags,
                    "source_type": "system",
                    "user_id": None,
                    "original_url": None,
                }
                
                content_index.append(searchable_content)
                processed_ids.add(arxiv_id)
            except Exception as e:
                logging.error(f"Error processing legacy MD file {md_path} for search index: {e}")
                continue

        self._cache["content_index"] = list(content_index)
        self._cache["count"] = count
        self._cache["latest_mtime"] = latest_mtime
        return content_index
    
    def _extract_searchable_content(self, record: SummaryRecord, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """Extract searchable content from SummaryRecord model."""
        try:
            # Extract title from PaperInfo
            title = self._extract_title_from_data(record, arxiv_id)
            
            # Extract content from SummaryData
            content = record.summary_data.markdown_content
            
            # If markdown content is empty, generate from structured content
            if not content:
                structured_summary = record.summary_data.structured_content
                content = structured_summary.to_markdown()
            
            # Extract tags from Tags model
            tags_obj = record.summary_data.tags
            top_tags = [str(t).strip().lower() for t in (tags_obj.top or []) if str(t).strip()]
            detail_tags = [str(t).strip().lower() for t in (tags_obj.tags or []) if str(t).strip()]
            tags = top_tags + detail_tags
            
            return {
                "id": arxiv_id,
                "title": title,
                "content": content,
                "tags": tags,
                "top_tags": top_tags,
                "detail_tags": detail_tags,
                "source_type": record.service_data.source_type or "system",
                "user_id": record.service_data.user_id,
                "original_url": record.service_data.original_url,
            }
        except Exception as e:
            logging.error(f"Error extracting searchable content for {arxiv_id}: {e}")
            return None
    
    def _extract_title_from_data(self, record: SummaryRecord, arxiv_id: str) -> str:
        """Extract title from SummaryRecord model."""
        # Try to get title from PaperInfo first
        paper_info = record.summary_data.structured_content.paper_info
        if paper_info.title_en:
            return paper_info.title_en
        
        # Try to extract from markdown content
        content = record.summary_data.markdown_content
        if content:
            title = self._extract_title_from_markdown(content)
            if title:
                return title
        
        # Fallback to arxiv_id
        return f"Paper {arxiv_id}"
    
    def _extract_title_from_markdown(self, content: str) -> str:
        """Extract title from markdown content."""
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            # Look for # title or ## title patterns
            if line.startswith('#') and len(line) > 1:
                title = line.lstrip('#').strip()
                if title:
                    return title
            # Look for **title** patterns
            elif line.startswith('**') and line.endswith('**') and len(line) > 4:
                title = line[2:-2].strip()
                if title:
                    return title
        return ""
    
    def search(self, query: str, search_fields: List[str] = None) -> List[Dict[str, Any]]:
        """Search papers by query across specified fields.
        
        Args:
            query: Search query string
            search_fields: List of fields to search in ['title', 'content', 'tags']
        
        Returns:
            List of matching papers with relevance scores
        """
        if not query or not query.strip():
            return []
        
        if search_fields is None:
            search_fields = ['title', 'content', 'tags']
        
        query = query.strip().lower()
        content_index = self._build_content_index()
        results = []
        
        for paper in content_index:
            score = 0
            matches = []
            
            # Search in title
            if 'title' in search_fields and paper.get('title'):
                title_matches = self._search_in_text(paper['title'], query)
                if title_matches:
                    score += title_matches * 3  # Higher weight for title matches
                    matches.extend([f"标题: {match}" for match in self._get_match_contexts(paper['title'], query)])
            
            # Search in content
            if 'content' in search_fields and paper.get('content'):
                content_matches = self._search_in_text(paper['content'], query)
                if content_matches:
                    score += content_matches
                    matches.extend([f"内容: {match}" for match in self._get_match_contexts(paper['content'], query)])
            
            # Search in tags
            if 'tags' in search_fields:
                tag_matches = 0
                for tag_list_name in ['tags', 'top_tags', 'detail_tags']:
                    tags = paper.get(tag_list_name, [])
                    for tag in tags:
                        if query in tag.lower():
                            tag_matches += 1
                            matches.append(f"标签: {tag}")
                
                if tag_matches:
                    score += tag_matches * 2  # Higher weight for tag matches
            
            if score > 0:
                results.append({
                    **paper,
                    'relevance_score': score,
                    'matches': matches[:5]  # Limit to 5 matches for display
                })
        
        # Sort by relevance score (highest first)
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results
    
    def _search_in_text(self, text: str, query: str) -> int:
        """Count occurrences of query in text (case-insensitive)."""
        if not text:
            return 0
        return len(re.findall(re.escape(query), text.lower()))
    
    def _get_match_contexts(self, text: str, query: str, context_length: int = 50) -> List[str]:
        """Get context around matches in text."""
        if not text:
            return []
        
        text_lower = text.lower()
        query_lower = query.lower()
        contexts = []
        
        start = 0
        while True:
            pos = text_lower.find(query_lower, start)
            if pos == -1:
                break
            
            # Get context around the match
            context_start = max(0, pos - context_length)
            context_end = min(len(text), pos + len(query) + context_length)
            context = text[context_start:context_end]
            
            # Clean up context
            if context_start > 0:
                context = "..." + context
            if context_end < len(text):
                context = context + "..."
            
            contexts.append(context.strip())
            start = pos + 1
        
        return contexts[:3]  # Limit to 3 contexts
    
    def clear_cache(self):
        """Clear the search index cache."""
        self._cache = {
            "content_index": None,
            "count": 0,
            "latest_mtime": 0.0,
        }
